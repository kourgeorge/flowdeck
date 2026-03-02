"""
FlowDeck LangGraph Chat Agent.

Architecture:
  ┌─────────────────────────────────────────────────────────────┐
  │                     FlowDeck Chat Graph                     │
  │                                                             │
  │  START → skill_router ──► skill_node ──► llm_synthesize    │
  │                    │                                        │
  │                    └──► react_agent (tool-calling loop)     │
  │                                                             │
  └─────────────────────────────────────────────────────────────┘

  1. skill_router:   Asks the LLM to select a skill (or none) based on the
                     skill descriptions loaded from SKILL.md files.
                     The LLM reads each skill's description and decides which
                     skill (if any) matches the user's intent, and extracts
                     the required arguments.  No regex or keyword matching.

  2. skill_node:     Runs the matched skill's sequential workflow (fetches
                     data from multiple tools in a deterministic order) and
                     injects the result into the system prompt context.

  3. react_agent:    LangGraph's built-in ReAct loop — the LLM decides which
                     tools to call, ToolNode executes them, loop continues
                     until the LLM produces a final answer.

  4. llm_synthesize: After a skill runs, calls the LLM once more to produce
                     a polished final answer from the skill's data context.

Skill discovery follows the agentskills.io standard:
  - Each skill has a SKILL.md with name + description frontmatter
  - At startup, only name + description are injected into the system prompt
  - The LLM decides which skill to activate and extracts arguments
  - The full SKILL.md instructions are loaded into context on activation

The graph is compiled once per process and reused across requests.
Per-request state (user_id, db, system_prompt) is passed via RunnableConfig.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from ai_engine.agent.state import AgentState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Planning & Task Complexity Analysis
# ---------------------------------------------------------------------------

_TASK_COMPLEXITY_PROMPT = """\
You are a task complexity analyzer for the FlowDeck financial assistant.

Analyze this user request and classify its complexity:

User Request: {user_message}

Classify as:
- "simple": Single-step query that can be answered directly
  Examples: "What's AAPL's price?", "Show me TSLA news", "What's the market doing?"
  
- "complex": Multi-step analysis requiring coordination but no user approval
  Examples: "Compare AAPL and MSFT performance", "Analyze my portfolio health"
  
- "long-horizon": Multi-phase task requiring planning and user approval
  Examples: "Build a comprehensive investment strategy for tech stocks",
           "Create a detailed quarterly market analysis report",
           "Develop a risk-adjusted portfolio allocation plan"

Consider:
1. Number of distinct steps required (1 = simple, 2-4 = complex, 5+ = long-horizon)
2. Need for user approval checkpoints
3. Multiple data sources and analysis phases
4. Iterative refinement requirements
5. Report generation or strategic planning

Respond ONLY with valid JSON:
{{
    "complexity": "simple|complex|long-horizon",
    "reasoning": "brief explanation",
    "estimated_steps": number,
    "requires_planning": boolean
}}
"""

_PLAN_CREATION_PROMPT = """\
Create a detailed execution plan for this long-horizon task:

User Request: {user_message}

Available Tools:
{tool_descriptions}

Available Skills:
{skill_descriptions}

Create a step-by-step plan with clear, actionable steps. Each step should:
1. Have a clear objective
2. Specify expected tools or skills to use
3. Include verification criteria
4. Note any dependencies on previous steps

Respond ONLY with valid JSON:
{{
    "todos": [
        {{
            "id": 1,
            "description": "Clear, actionable step description",
            "dependencies": [],
            "estimated_complexity": "low|medium|high",
            "expected_tools": ["tool1", "tool2"],
            "verification": "How to verify this step succeeded"
        }}
    ],
    "explanation": "Brief overview of the plan for the user",
    "estimated_duration": "estimated time (e.g., '2-3 minutes')"
}}
"""


def _analyze_task_complexity(llm: Any, user_message: str) -> Dict[str, Any]:
    """
    Use LLM to classify task complexity.
    
    Returns dict with: complexity, reasoning, estimated_steps, requires_planning
    """
    try:
        prompt = _TASK_COMPLEXITY_PROMPT.format(user_message=user_message)
        response = llm.invoke([SystemMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)
        
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        result = json.loads(content)
        logger.info("Task complexity analysis: %s", result)
        return result
    except Exception as exc:
        logger.warning("Task complexity analysis failed: %s — defaulting to simple", exc)
        return {
            "complexity": "simple",
            "reasoning": "Analysis failed, treating as simple query",
            "estimated_steps": 1,
            "requires_planning": False
        }


def _create_task_plan(llm: Any, user_message: str, state: AgentState) -> Dict[str, Any]:
    """
    Create a detailed execution plan for a long-horizon task.
    
    Returns dict with: todos, explanation, estimated_duration
    """
    from ai_engine.agent.skills import SKILL_DESCRIPTIONS
    from ai_engine.agent.lc_tools import get_all_lc_tools
    
    # Get tool descriptions
    user_id = state.get("user_id")
    db = state.get("db")
    tools = get_all_lc_tools(user_id=user_id, db=db)
    tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools[:15]])  # Limit to avoid token overflow
    
    # Get skill descriptions
    skill_descriptions = "\n".join([f"- {name}: {desc}" for name, desc in SKILL_DESCRIPTIONS.items()])
    
    try:
        prompt = _PLAN_CREATION_PROMPT.format(
            user_message=user_message,
            tool_descriptions=tool_descriptions,
            skill_descriptions=skill_descriptions
        )
        response = llm.invoke([SystemMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)
        
        # Strip markdown code fences
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        plan = json.loads(content)
        
        # Add status field to each todo
        for todo in plan.get("todos", []):
            todo["status"] = "pending"
            todo["actual_tools_used"] = []
        
        logger.info("Created plan with %d steps", len(plan.get("todos", [])))
        return plan
    except Exception as exc:
        logger.error("Plan creation failed: %s", exc)
        return {
            "todos": [],
            "explanation": "Failed to create plan. Will proceed with direct execution.",
            "estimated_duration": "unknown"
        }


def _format_plan_for_user(todo_list: List[Dict[str, Any]]) -> str:
    """Format the todo list as a readable plan for the user."""
    if not todo_list:
        return "No steps planned."
    
    lines = []
    for i, todo in enumerate(todo_list, 1):
        status_icon = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "blocked": "❌"
        }.get(todo.get("status", "pending"), "⏳")
        
        lines.append(f"{status_icon} **Step {i}**: {todo.get('description', 'Unknown step')}")
        
        if todo.get("dependencies"):
            dep_str = ", ".join([f"Step {d}" for d in todo["dependencies"]])
            lines.append(f"   *Depends on: {dep_str}*")
        
        complexity = todo.get("estimated_complexity", "medium")
        lines.append(f"   *Complexity: {complexity}*")
        lines.append("")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Node: planning_node
# ---------------------------------------------------------------------------

def planning_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Analyze the user's request and determine if planning is needed.
    For long-horizon tasks, create a detailed todo list.
    """
    messages = state.get("messages", [])
    
    # Get last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content if isinstance(msg.content, str) else ""
            break
    
    if not last_user_msg:
        return {
            "task_type": "simple",
            "planning_phase": "executing"
        }
    
    llm = (config or {}).get("configurable", {}).get("llm")
    if llm is None:
        logger.warning("planning_node | no LLM in config, skipping planning")
        return {
            "task_type": "simple",
            "planning_phase": "executing"
        }
    
    # Analyze task complexity
    analysis = _analyze_task_complexity(llm, last_user_msg)
    complexity = analysis.get("complexity", "simple")
    
    if complexity == "simple":
        logger.info("planning_node | simple task, skipping planning")
        return {
            "task_type": "simple",
            "planning_phase": "executing"
        }
    
    if complexity == "complex":
        # Complex tasks don't need approval, just proceed
        logger.info("planning_node | complex task, proceeding without approval")
        return {
            "task_type": "complex",
            "planning_phase": "executing"
        }
    
    # Long-horizon task: create a plan
    logger.info("planning_node | long-horizon task, creating plan")
    plan = _create_task_plan(llm, last_user_msg, state)
    
    if not plan.get("todos"):
        # Plan creation failed, fall back to simple execution
        return {
            "task_type": "simple",
            "planning_phase": "executing"
        }
    
    return {
        "task_type": "long-horizon",
        "planning_phase": "awaiting_approval",
        "todo_list": plan["todos"],
        "plan_approved": False,
        "current_step": 0,
        "discoveries": [],
        "messages": [SystemMessage(
            content=f"[PLAN_CREATED] {plan['explanation']}\n\nEstimated duration: {plan.get('estimated_duration', 'unknown')}"
        )]
    }


def route_after_planning(state: AgentState) -> Literal["plan_approval", "skill_router"]:
    """Route after planning: if long-horizon, go to approval; otherwise continue to skill_router."""
    task_type = state.get("task_type")
    if task_type == "long-horizon" and state.get("planning_phase") == "awaiting_approval":
        return "plan_approval"
    return "skill_router"


# ---------------------------------------------------------------------------
# Node: plan_approval_node
# ---------------------------------------------------------------------------

def plan_approval_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Present the plan to the user and wait for approval.
    This node emits the plan and then waits for the next user message.
    """
    todo_list = state.get("todo_list", [])
    
    if not todo_list:
        return {
            "planning_phase": "executing",
            "plan_approved": True
        }
    
    # Format plan for user
    plan_text = _format_plan_for_user(todo_list)
    
    approval_msg = AIMessage(content=f"""I've analyzed your request and created this execution plan:

{plan_text}

**Total Steps**: {len(todo_list)}

Would you like me to proceed with this plan? You can:
- Say "yes" or "proceed" to start execution
- Request modifications (e.g., "skip step 2" or "add analysis of X")
- Say "cancel" to try a different approach
""")
    
    return {
        "messages": [approval_msg],
        "planning_phase": "awaiting_approval"
    }


def route_after_plan_approval(state: AgentState) -> Literal["skill_router", "END"]:
    """
    After presenting the plan, check if user approved.
    This is called after the user responds to the approval request.
    """
    # Check if the user's response indicates approval
    messages = state.get("messages", [])
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content if isinstance(msg.content, str) else ""
            break
    
    # Simple approval detection (can be enhanced with LLM)
    approval_keywords = ["yes", "proceed", "go ahead", "start", "continue", "ok", "sure"]
    cancel_keywords = ["no", "cancel", "stop", "nevermind", "different"]
    
    last_user_lower = last_user_msg.lower()
    
    if any(kw in last_user_lower for kw in cancel_keywords):
        logger.info("plan_approval | user cancelled plan")
        return "END"
    
    if any(kw in last_user_lower for kw in approval_keywords):
        logger.info("plan_approval | user approved plan")
        return "skill_router"
    
    # If unclear, assume approval for now (can be enhanced)
    logger.info("plan_approval | unclear response, assuming approval")
    return "skill_router"


# ---------------------------------------------------------------------------
# Skill router: LLM-based selection using SKILL.md descriptions
# ---------------------------------------------------------------------------

_SKILL_ROUTER_SYSTEM = """\
You are a skill router for the FlowDeck financial assistant.

Your job is to decide whether the user's message should be handled by one of
the available skills listed below, or by the general tool-calling agent.

Available skills:
{skill_list}

Instructions:
- Read the user's message carefully.
- If it clearly matches one of the skill descriptions, return a JSON object
  with the skill name and any required arguments extracted from the message.
- If no skill matches, return {{"skill": null}}.

For the "compare_stocks" skill:
  - Resolve natural-language market names to ticker symbols:
      "usa", "us market", "s&p", "s&p 500" → "^GSPC"
      "nasdaq", "nasdaq 100" → "^IXIC"
      "dow", "dow jones" → "^DJI"
      "israel", "israeli market", "ta-35", "ta35", "tel aviv" → "TA35.TA"
      "ftse", "uk market" → "^FTSE"
      "dax", "german market" → "^GDAXI"
      "nikkei", "japan" → "^N225"
  - If the user mentions a time period (e.g. "last month", "this week", "last year",
    "in the last month", "over the past year", "ytd"), extract it as "period":
      "last month" / "past month" → "month"
      "this month" → "this month"
      "last week" / "past week" → "week"
      "this week" → "this week"
      "year to date" / "ytd" → "ytd"
      "last year" / "past year" / "1 year" → "1y"
      "last 3 months" / "3 months" → "3m"
      "last 6 months" / "6 months" → "6m"
    If no period is mentioned, omit the "period" key entirely.

For the "stock_deep_dive" skill:
  - Extract the single ticker symbol.
  - ONLY activate for explicit deep-dive / full-analysis requests:
      "deep dive", "full analysis", "complete analysis", "tell me everything about",
      "comprehensive report", "full report", "deep analysis"
  - Do NOT activate for simple questions like:
      "what is the recommendation for X", "what's the price of X",
      "how is X doing", "should I buy X", "what do you think about X"
    These should be handled by the general agent (skill: null).

For the "portfolio_performance" skill:
  - Extract the period (e.g. "last month" → "month", "this week" → "this week").
  - Default to "week" if not specified.

For the "portfolio_health" skill:
  - No arguments needed.

Respond ONLY with a valid JSON object. Examples:
  {{"skill": "compare_stocks", "args": {{"tickers": ["^GSPC", "TA35.TA"], "period": "month"}}}}
  {{"skill": "compare_stocks", "args": {{"tickers": ["AAPL", "MSFT"]}}}}
  {{"skill": "stock_deep_dive", "args": {{"ticker": "AAPL"}}}}
  {{"skill": "portfolio_health", "args": {{}}}}
  {{"skill": "portfolio_performance", "args": {{"period": "month"}}}}
  {{"skill": null}}
"""


def _build_skill_list_text() -> str:
    """Build a formatted skill list from SKILL.md descriptions for the router prompt."""
    from ai_engine.agent.skills import SKILL_DESCRIPTIONS
    lines = []
    for name, description in SKILL_DESCRIPTIONS.items():
        lines.append(f"- **{name}**: {description}")
    return "\n".join(lines)


def _llm_select_skill(llm: Any, user_message: str) -> tuple[Optional[str], dict]:
    """
    Ask the LLM to select a skill and extract arguments from the user message.

    Returns (skill_name_or_None, args_dict).
    """
    skill_list = _build_skill_list_text()
    system_prompt = _SKILL_ROUTER_SYSTEM.format(skill_list=skill_list)

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        content = response.content if isinstance(response.content, str) else str(response.content)

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        skill_name = parsed.get("skill")
        args = parsed.get("args", {}) or {}

        if skill_name:
            logger.info("skill_router | LLM selected skill=%s args=%s", skill_name, args)
        else:
            logger.info("skill_router | LLM selected no skill")

        return skill_name, args

    except Exception as exc:
        logger.warning("skill_router | LLM skill selection failed: %s — falling back to react_agent", exc)
        return None, {}


# ---------------------------------------------------------------------------
# Node: skill_router
# ---------------------------------------------------------------------------

def skill_router_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Inspect the last user message and use the LLM to decide whether to route
    to a skill or directly to the ReAct tool-calling loop.

    The LLM reads skill descriptions from SKILL.md files (agentskills.io standard)
    and selects the appropriate skill + extracts arguments.

    Sets state["skill_used"] and state["skill_args"].
    Does NOT modify messages — just sets routing metadata.
    """
    messages = state.get("messages", [])
    last_user = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user = msg.content if isinstance(msg.content, str) else ""
            break

    if not last_user:
        return {"skill_used": None, "skill_args": {}}

    llm = (config or {}).get("configurable", {}).get("llm")
    if llm is None:
        logger.warning("skill_router | no LLM in config, skipping skill routing")
        return {"skill_used": None, "skill_args": {}}

    skill_name, skill_args = _llm_select_skill(llm, last_user)
    return {"skill_used": skill_name, "skill_args": skill_args}


def route_after_skill_router(state: AgentState) -> Literal["skill_node", "react_agent"]:
    """Conditional edge: go to skill_node if a skill matched, else react_agent."""
    return "skill_node" if state.get("skill_used") else "react_agent"


# ---------------------------------------------------------------------------
# Node: skill_node
# ---------------------------------------------------------------------------

def skill_node(state: AgentState) -> Dict[str, Any]:
    """
    Run the matched skill's sequential workflow.

    Uses the arguments extracted by the LLM in skill_router_node.
    Injects the skill result into the message history as a SystemMessage
    so the subsequent llm_synthesize node can use it.

    On activation, loads the full SKILL.md body into context so the LLM
    has the complete instructions when synthesizing the final answer.
    """
    from ai_engine.agent.tool import ExecutionContext
    from ai_engine.agent.executor import ToolExecutor
    from ai_engine.agent.registry import ToolRegistry
    from ai_engine.agent.tools import ALL_TOOLS
    from ai_engine.agent.tools.user_context import make_user_context_tools
    from ai_engine.agent.skills import ALL_SKILLS, load_skill_md
    from ai_engine.agent.registry import SkillRegistry

    skill_name = state.get("skill_used")
    skill_args = state.get("skill_args") or {}
    user_id = state.get("user_id")
    db = state.get("db")
    max_tool_calls = state.get("max_tool_calls", 15)

    # Build tool registry
    tool_registry = ToolRegistry()
    tool_registry.register_many(ALL_TOOLS)
    if user_id is not None and db is not None:
        tool_registry.register_many(make_user_context_tools(user_id, db))

    tool_executor = ToolExecutor()
    tool_executor.tool_registry = tool_registry  # type: ignore[attr-defined]

    # Build skill registry and find the skill
    skill_registry = SkillRegistry()
    skill_registry.register_many(ALL_SKILLS)
    if not skill_name:
        return {"skill_used": None}

    skill = skill_registry.get(skill_name)
    if skill is None:
        logger.warning("skill_node | skill '%s' not found, falling back", skill_name)
        return {"skill_used": None}

    ctx = ExecutionContext(user_id=user_id, db=db, max_tool_calls=max_tool_calls)

    from ai_engine.agent.executor import SkillExecutor
    skill_executor = SkillExecutor(tool_executor=tool_executor)
    skill_result = skill_executor.run(skill, ctx, **skill_args)

    if skill_result.ok:
        # Load the full SKILL.md body for richer synthesis context
        skill_md = load_skill_md(skill_name) or ""

        context_block = (
            f"\n\n## Skill Activated: {skill_name}\n"
            f"{skill_md}\n\n"
            f"## Skill Workflow Result\n"
            f"The following data was gathered by running the '{skill_name}' workflow:\n\n"
            f"{skill_result.to_str()}\n\n"
            f"Use this data to answer the user's question. Do NOT call tools to re-fetch "
            f"data already present above."
        )

        # Serialize skill steps for SSE streaming
        raw_steps = getattr(skill_result, "steps", []) or []
        skill_steps = []
        for step in raw_steps:
            try:
                args = getattr(step, "args", {}) or {}
                result = getattr(step, "result", None)
                output = result.to_str()[:500] if result is not None else ""
                skill_steps.append({
                    "tool": getattr(step, "tool_name", ""),
                    "input": json.dumps(args) if isinstance(args, dict) else str(args),
                    "output": output,
                    "ok": bool(getattr(step, "ok", True)),
                })
            except Exception:
                pass

        logger.info(
            "skill_node | skill=%s ok=True | steps=%d",
            skill_name,
            len(skill_result.steps),
        )
        return {
            "messages": [SystemMessage(content=context_block, name="skill_context")],
            "skill_steps": skill_steps,
        }
    else:
        logger.warning(
            "skill_node | skill=%s failed | error=%s | falling back to react_agent",
            skill_name,
            skill_result.error,
        )
        return {"skill_used": None}


def route_after_skill_node(state: AgentState) -> Literal["llm_synthesize", "react_agent"]:
    """
    After skill_node: if skill succeeded (skill_used still set), go to llm_synthesize.
    If skill failed (skill_used was cleared), fall back to react_agent.
    """
    return "llm_synthesize" if state.get("skill_used") else "react_agent"


# ---------------------------------------------------------------------------
# Node: llm_synthesize  (post-skill final answer)
# ---------------------------------------------------------------------------

def llm_synthesize_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """
    After a skill runs, call the LLM once to produce a polished final answer
    from the skill data that was injected into the message history.

    Appends a HumanMessage reminding the LLM of the user's original question
    so it answers specifically rather than just summarizing the skill data.
    """
    llm = config.get("configurable", {}).get("llm")
    if llm is None:
        raise RuntimeError("llm_synthesize_node: 'llm' not found in RunnableConfig configurable")

    messages = list(state.get("messages", []))

    # Find the user's original question to anchor the synthesis
    user_question = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_question = msg.content if isinstance(msg.content, str) else ""
            break

    if user_question:
        messages = messages + [
            HumanMessage(
                content=(
                    f"Using ONLY the data provided above by the skill workflow, "
                    f"please answer the user's question: {user_question}\n\n"
                    f"Be specific and direct. Do not call any tools — all data is already above."
                )
            )
        ]

    response = llm.invoke(messages)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Build the compiled graph
# ---------------------------------------------------------------------------

def build_graph(tools: list) -> Any:
    """
    Build and compile the FlowDeck chat agent StateGraph.

    Args:
        tools: List of LangChain @tool functions for the ReAct loop.

    Returns:
        A compiled LangGraph graph (CompiledStateGraph).
    """
    tool_node = ToolNode(tools)

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planning", planning_node)
    graph.add_node("plan_approval", plan_approval_node)
    graph.add_node("skill_router", skill_router_node)
    graph.add_node("skill_node", skill_node)
    graph.add_node("llm_synthesize", llm_synthesize_node)
    graph.add_node("tool_node", tool_node)
    graph.add_node("call_model", _call_model_node)

    # Edges
    # START → planning → (plan_approval if long-horizon | skill_router otherwise)
    graph.add_edge(START, "planning")
    graph.add_conditional_edges(
        "planning",
        route_after_planning,
        {"plan_approval": "plan_approval", "skill_router": "skill_router"},
    )
    
    # plan_approval → (skill_router if approved | END if cancelled)
    graph.add_conditional_edges(
        "plan_approval",
        route_after_plan_approval,
        {"skill_router": "skill_router", "END": END},
    )
    
    # skill_router → (skill_node if skill matched | call_model for ReAct)
    graph.add_conditional_edges(
        "skill_router",
        route_after_skill_router,
        {"skill_node": "skill_node", "react_agent": "call_model"},
    )
    
    # skill_node → (llm_synthesize if succeeded | call_model if failed)
    graph.add_conditional_edges(
        "skill_node",
        route_after_skill_node,
        {"llm_synthesize": "llm_synthesize", "react_agent": "call_model"},
    )
    graph.add_edge("llm_synthesize", END)

    # ReAct loop: call_model → (tool_node → call_model)* → END
    graph.add_conditional_edges(
        "call_model",
        _route_after_call_model,
        {"tools": "tool_node", "end": END},
    )
    graph.add_edge("tool_node", "call_model")

    return graph.compile()


# ---------------------------------------------------------------------------
# ReAct loop nodes
# ---------------------------------------------------------------------------

def _call_model_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Call the LLM with the current message history (with tools bound if supported)."""
    cfg = (config or {}).get("configurable", {})
    llm = cfg.get("llm")
    tools = cfg.get("tools", [])

    if llm is None:
        raise RuntimeError("_call_model_node: 'llm' not found in RunnableConfig configurable")

    messages = list(state.get("messages", []))

    # Enforce max_tool_calls budget
    tool_calls_made = state.get("tool_calls_made", 0)
    max_tool_calls = state.get("max_tool_calls", 15)

    if tool_calls_made >= max_tool_calls:
        logger.warning("_call_model_node | max_tool_calls=%d reached, forcing final answer", max_tool_calls)
        response = llm.invoke(messages)
    elif tools:
        try:
            llm_with_tools = llm.bind_tools(tools)
            response = llm_with_tools.invoke(messages)
        except NotImplementedError:
            response = llm.invoke(messages)
    else:
        response = llm.invoke(messages)

    return {"messages": [response]}


def _route_after_call_model(
    state: AgentState,
) -> Literal["tools", "end"]:
    """Route to tool_node if the LLM made tool calls, else END."""
    messages = state.get("messages", [])
    last_msg = messages[-1] if messages else None
    if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", None):
        tool_calls_made = state.get("tool_calls_made", 0)
        max_tool_calls = state.get("max_tool_calls", 15)
        if tool_calls_made < max_tool_calls:
            return "tools"
    return "end"


# ---------------------------------------------------------------------------
# Public API: FlowDeckAgent
# ---------------------------------------------------------------------------

class FlowDeckAgent:
    """
    LangGraph-based chat agent for FlowDeck.

    Skill routing follows the agentskills.io standard:
      - Each skill has a SKILL.md with name + description
      - The LLM reads skill descriptions and selects the appropriate skill
      - No regex or keyword matching — the LLM understands natural language
      - Full SKILL.md instructions are loaded into context on activation

    Usage:
        agent = FlowDeckAgent(llm)
        result = agent.run(messages, user_id=42, db=session, system_prompt="...")
        for event in agent.stream(messages, user_id=42, db=session, system_prompt="..."):
            ...
    """

    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self._graphs: Dict[str, Any] = {}  # keyed by tool fingerprint

    def _get_graph(self, tools: list) -> Any:
        """Get or build a compiled graph for the given tool set."""
        key = str([getattr(t, "name", str(t)) for t in tools])
        if key not in self._graphs:
            self._graphs[key] = build_graph(tools)
        return self._graphs[key]

    def _make_config(
        self,
        tools: list,
        user_id: Optional[int],
        db: Any,
        system_prompt: str,
        max_tool_calls: int,
    ) -> RunnableConfig:
        """Build the RunnableConfig for a request."""
        from ai_engine.agent.tool import ExecutionContext
        return {
            "configurable": {
                "llm": self.llm,
                "tools": tools,
                "execution_context": ExecutionContext(
                    user_id=user_id,
                    db=db,
                    max_tool_calls=max_tool_calls,
                ),
            }
        }

    def _make_initial_state(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int],
        db: Any,
        system_prompt: str,
        max_tool_calls: int,
    ) -> AgentState:
        """Convert raw message dicts to LangChain messages and build initial state."""
        from ai_engine.agent.skills import SKILL_DESCRIPTIONS

        # Build skill discovery block for the system prompt
        skill_lines = [
            "## Available Skills",
            "The following skills are available. When a user request matches a skill's "
            "description, the skill workflow will be activated automatically:",
            "",
        ]
        for name, description in SKILL_DESCRIPTIONS.items():
            skill_lines.append(f"- **{name}**: {description}")

        skill_block = "\n".join(skill_lines)
        full_system_prompt = f"{system_prompt}\n\n{skill_block}" if system_prompt else skill_block

        lc_messages: List[Any] = [SystemMessage(content=full_system_prompt)]
        for msg in messages[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            else:
                lc_messages.append(AIMessage(content=content))

        return {
            "messages": lc_messages,
            "user_id": user_id,
            "db": db,
            "max_tool_calls": max_tool_calls,
            "tool_calls_made": 0,
            "skill_used": None,
            "skill_args": {},
            "skill_steps": [],
            "system_prompt": system_prompt,
            "context": None,
            "error": None,
            # Planning & Todo Management
            "task_type": None,
            "planning_phase": None,
            "todo_list": None,
            "current_step": None,
            "plan_approved": False,
            "discoveries": None,
        }

    def run(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        db: Any = None,
        system_prompt: str = "",
        max_tool_calls: int = 15,
    ) -> Dict[str, Any]:
        """
        Run a full agent turn (blocking).

        Returns:
            {"reply": str, "tokens_used": int, "tools_called": int, "skill_used": str | None}
        """
        from ai_engine.agent.lc_tools import get_all_lc_tools
        tools = get_all_lc_tools(user_id=user_id, db=db)
        graph = self._get_graph(tools)
        config = self._make_config(tools, user_id, db, system_prompt, max_tool_calls)
        initial_state = self._make_initial_state(messages, user_id, db, system_prompt, max_tool_calls)

        try:
            final_state = graph.invoke(initial_state, config=config)
        except Exception as exc:
            logger.exception("FlowDeckAgent.run | error | user_id=%s | %s", user_id, exc)
            return {
                "reply": f"I encountered an error while processing your request: {exc}. Please try again.",
                "tokens_used": 1,
                "tools_called": 0,
                "skill_used": None,
            }

        final_messages = final_state.get("messages", [])
        reply = ""
        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content:
                reply = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        tools_called = sum(
            1 for msg in final_messages
            if isinstance(msg, ToolMessage)
        )

        return {
            "reply": reply,
            "tokens_used": max(1, 1 + tools_called),
            "tools_called": tools_called,
            "skill_used": final_state.get("skill_used"),
        }

    def stream(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[int] = None,
        db: Any = None,
        system_prompt: str = "",
        max_tool_calls: int = 15,
    ) -> Generator[str, None, None]:
        """
        Run a full agent turn and yield SSE events.

        Yields SSE-formatted strings compatible with the existing frontend protocol:
          - data: {"type":"thinking","content":"..."}
          - data: {"type":"skill_start","name":"..."}
          - data: {"type":"skill_done","name":"...","steps":N}
          - data: {"type":"tool_call","name":"...","input":"...","output":"..."}
          - data: {"type":"token","content":"..."}
          - data: {"type":"done","tokens_used":N,"tools_called":M,"skill_used":"..."}
          - data: {"type":"error","content":"..."}
        """
        from ai_engine.agent.lc_tools import get_all_lc_tools
        tools = get_all_lc_tools(user_id=user_id, db=db)
        graph = self._get_graph(tools)
        config = self._make_config(tools, user_id, db, system_prompt, max_tool_calls)
        initial_state = self._make_initial_state(messages, user_id, db, system_prompt, max_tool_calls)

        tools_called = 0
        skill_used = None
        pending_tool_inputs: Dict[str, str] = {}

        try:
            for chunk in graph.stream(
                initial_state,
                config=config,
                stream_mode="updates",
            ):
                for node_name, event_data in chunk.items():

                    # planning node analyzed task
                    if node_name == "planning":
                        task_type = event_data.get("task_type")
                        if task_type == "long-horizon":
                            yield f"data: {json.dumps({'type': 'thinking', 'content': 'Analyzing task complexity...'})}\n\n"
                            todo_list = event_data.get("todo_list", [])
                            if todo_list:
                                yield f"data: {json.dumps({'type': 'plan_created', 'todos': todo_list, 'task_type': task_type})}\n\n"
                        elif task_type in ["simple", "complex"]:
                            yield f"data: {json.dumps({'type': 'thinking', 'content': f'Task classified as {task_type}, proceeding...'})}\n\n"
                    
                    # plan_approval node presented plan
                    elif node_name == "plan_approval":
                        planning_phase = event_data.get("planning_phase")
                        if planning_phase == "awaiting_approval":
                            yield f"data: {json.dumps({'type': 'awaiting_approval', 'content': 'Plan ready for your review'})}\n\n"

                    # skill_router fired
                    elif node_name == "skill_router":
                        matched = event_data.get("skill_used")
                        if matched:
                            skill_used = matched
                            yield f"data: {json.dumps({'type': 'skill_start', 'name': matched})}\n\n"
                            yield f"data: {json.dumps({'type': 'thinking', 'content': f'Running {matched} workflow...'})}\n\n"

                    # skill_node completed
                    elif node_name == "skill_node":
                        # skill_node only sets skill_used=None in the failure path.
                        # On success it returns {"messages": [...], "skill_steps": [...]}.
                        # So we check for the explicit failure sentinel, not absence of the key.
                        skill_failed = "skill_used" in event_data and event_data["skill_used"] is None
                        if skill_failed:
                            skill_used = None
                        if skill_used:
                            # Emit each tool step the skill executed
                            skill_steps = event_data.get("skill_steps", [])
                            for step in skill_steps:
                                yield f"data: {json.dumps({'type': 'skill_step', 'skill': skill_used, 'tool': step.get('tool', ''), 'input': step.get('input', ''), 'output': step.get('output', ''), 'ok': step.get('ok', True)})}\n\n"
                            yield f"data: {json.dumps({'type': 'skill_done', 'name': skill_used, 'steps': len(skill_steps)})}\n\n"

                    # tool_node executed tools
                    elif node_name == "tool_node":
                        new_messages = event_data.get("messages", [])
                        for msg in new_messages:
                            if isinstance(msg, ToolMessage):
                                tools_called += 1
                                tool_name = msg.name or "tool"
                                output = msg.content if isinstance(msg.content, str) else str(msg.content)
                                tool_input = pending_tool_inputs.pop(
                                    getattr(msg, "tool_call_id", ""), ""
                                )
                                yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'input': tool_input, 'output': output})}\n\n"

                    # call_model or llm_synthesize produced a response
                    elif node_name in ("call_model", "llm_synthesize"):
                        new_messages = event_data.get("messages", [])
                        for msg in new_messages:
                            if isinstance(msg, AIMessage):
                                for tc in (getattr(msg, "tool_calls", None) or []):
                                    tc_id = tc.get("id", "")
                                    tc_args = tc.get("args", {})
                                    if tc_id:
                                        try:
                                            pending_tool_inputs[tc_id] = json.dumps(tc_args)
                                        except Exception:
                                            pending_tool_inputs[tc_id] = str(tc_args)

                                if msg.content:
                                    if not getattr(msg, "tool_calls", None):
                                        content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                                    else:
                                        tool_names = [tc.get("name", "?") for tc in (msg.tool_calls or [])]
                                        names_str = ", ".join(tool_names)
                                        yield f"data: {json.dumps({'type': 'thinking', 'content': f'Calling {names_str}...'})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'tokens_used': max(1, 1 + tools_called), 'tools_called': tools_called, 'skill_used': skill_used})}\n\n"

        except Exception as exc:
            logger.exception("FlowDeckAgent.stream | error | user_id=%s | %s", user_id, exc)
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"

# Made with Bob
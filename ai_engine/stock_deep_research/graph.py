"""
Stock Deep Research LangGraph: research brief → supervisor (delegate) → researchers (search + optional EDGAR) → final report.
"""

import asyncio
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .config import StockDeepResearchConfig
from .prompts import (
    COMPRESS_RESEARCH_HUMAN,
    COMPRESS_RESEARCH_SYSTEM,
    FINAL_REPORT_GENERATION_PROMPT,
    LEAD_RESEARCHER_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    TRANSFORM_MESSAGES_INTO_RESEARCH_BRIEF,
    RESEARCH_BRIEF_SYSTEM,
)
from .state import (
    AgentState,
    AgentInputState,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    StockResearchQuestion,
    SupervisorState,
)
from .tools import get_all_tools
from ai_engine.llm_provider import get_config_from_env, get_llm


def _split_provider_model(model: str) -> tuple[str, str]:
    """Split an init_chat_model-style name (e.g. openai:gpt-4o) into (provider, model)."""
    if not model:
        return "openai", "gpt-4o"
    if ":" in model:
        provider, name = model.split(":", 1)
        return provider.strip().lower() or "openai", name.strip()
    return "openai", model


def _get_chat_model(model: str, max_tokens: int, config: Optional[RunnableConfig]):
    """Build a chat model for an init_chat_model-style name via the shared LLM provider factory."""
    provider, name = _split_provider_model(model)
    conf = (config or {}).get("configurable") or {}
    llm_config = get_config_from_env({**conf, "llm_provider": provider})
    return get_llm("quick", llm_config, model_name=name, max_tokens=max_tokens)


def _get_today_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%a %b %d, %Y")


def _notes_from_tool_messages(messages):
    from langchain_core.messages import filter_messages
    return [m.content for m in filter_messages(messages, include_types=["tool"])]


# --- 1) Write research brief ---
async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command[Literal["research_supervisor"]]:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    messages = state.get("messages", [])
    from langchain_core.messages import get_buffer_string
    prompt_content = TRANSFORM_MESSAGES_INTO_RESEARCH_BRIEF.format(
        messages=get_buffer_string(messages),
        date=_get_today_str(),
    )
    model = (
        _get_chat_model(cfg.research_model, cfg.research_model_max_tokens, config)
        .with_structured_output(StockResearchQuestion)
        .with_retry(stop_after_attempt=cfg.max_structured_output_retries)
    )
    response = await model.ainvoke([SystemMessage(content=RESEARCH_BRIEF_SYSTEM), HumanMessage(content=prompt_content)])
    brief = response.research_brief
    supervisor_system = LEAD_RESEARCHER_PROMPT.format(
        date=_get_today_str(),
        max_concurrent_research_units=cfg.max_concurrent_research_units,
        research_brief=brief,
    )
    return Command(
        goto="research_supervisor",
        update={
            "research_brief": brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system),
                    HumanMessage(content=brief),
                ],
            },
        },
    )


# --- 2) Supervisor ---
async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    from .tools import think_tool
    lead_tools = [ConductResearch, ResearchComplete, think_tool]
    model = (
        _get_chat_model(cfg.research_model, cfg.research_model_max_tokens, config)
        .bind_tools(lead_tools)
        .with_retry(stop_after_attempt=cfg.max_structured_output_retries)
    )
    supervisor_messages = state.get("supervisor_messages", [])
    response = await model.ainvoke(supervisor_messages)
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


# --- Supervisor subgraph: supervisor_tools added after researcher_subgraph is compiled ---
supervisor_builder = StateGraph(SupervisorState)
supervisor_builder.add_node("supervisor", supervisor)
supervisor_builder.add_edge(START, "supervisor")


# --- 3) Researcher node ---
async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher_tools", "compress_research"]]:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    tools = await get_all_tools(config)
    researcher_messages = state.get("researcher_messages", [])
    topic = state.get("research_topic", "")
    system = RESEARCHER_SYSTEM_PROMPT.format(date=_get_today_str(), research_topic=topic)
    model = (
        _get_chat_model(cfg.research_model, cfg.research_model_max_tokens, config)
        .bind_tools(tools)
        .with_retry(stop_after_attempt=cfg.max_structured_output_retries)
    )
    messages = [SystemMessage(content=system)] + researcher_messages
    response = await model.ainvoke(messages)
    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        # No tools called -> go straight to compression with this message
        return Command(
            goto="compress_research",
            update={
                "researcher_messages": [response],
                "_next": "compress_research",
            },
        )
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
            "_next": "researcher_tools",
        },
    )


async def _run_tool(tool, args: dict, config: RunnableConfig):
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(args, config)
    if callable(tool):
        return await asyncio.to_thread(tool.invoke, args) if hasattr(tool, "invoke") else tool(**args)
    return "Tool not runnable"


async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher", "compress_research"]]:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    last_msg = researcher_messages[-1] if researcher_messages else None
    tool_calls = getattr(last_msg, "tool_calls", None) or []

    if not tool_calls:
        return Command(goto="compress_research", update={"_next": "compress_research"})

    tools_list = await get_all_tools(config)
    by_name = {}
    for t in tools_list:
        n = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else None)
        if n:
            by_name[n] = t

    outputs = []
    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("args", {})
        tid = tc.get("id", "")
        tool_obj = by_name.get(name)
        if tool_obj:
            try:
                result = await _run_tool(tool_obj, args, config)
                content = result if isinstance(result, str) else str(result)
            except Exception as e:
                content = f"Error: {e}"
        else:
            content = f"Unknown tool: {name}"
        outputs.append(ToolMessage(content=content, tool_call_id=tid, name=name or "tool"))

    iters = state.get("tool_call_iterations", 0)
    if iters >= cfg.max_react_tool_calls or any(t.get("name") == "ResearchComplete" for t in tool_calls):
        return Command(goto="compress_research", update={"researcher_messages": outputs, "_next": "compress_research"})

    return Command(goto="researcher", update={"researcher_messages": outputs, "_next": "researcher"})


async def compress_research(state: ResearcherState, config: RunnableConfig) -> dict:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    from langchain_core.messages import filter_messages
    raw = "\n".join(
        m.content for m in filter_messages(researcher_messages, include_types=["tool", "ai"])
        if hasattr(m, "content") and m.content
    )
    compression_prompt = COMPRESS_RESEARCH_SYSTEM.format(date=_get_today_str())
    messages = [SystemMessage(content=compression_prompt)] + researcher_messages + [HumanMessage(content=COMPRESS_RESEARCH_HUMAN)]
    model = _get_chat_model(cfg.compression_model, cfg.compression_model_max_tokens, config)
    try:
        response = await model.ainvoke(messages)
        compressed = response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        compressed = f"Compression failed: {e}. Raw notes: {raw[:8000]}"
    return {"compressed_research": compressed, "raw_notes": [raw]}


# --- Researcher subgraph ---
def _researcher_tools_route(state: ResearcherState) -> str:
    return state.get("_next", "researcher")

def _researcher_route(state: ResearcherState) -> str:
    """From researcher node: go to compress_research if _next is set (no tool calls), else researcher_tools."""
    return state.get("_next", "researcher_tools")

researcher_builder = StateGraph(ResearcherState, output=ResearcherOutputState)
researcher_builder.add_node("researcher", researcher)
researcher_builder.add_node("researcher_tools", researcher_tools)
researcher_builder.add_node("compress_research", compress_research)
researcher_builder.add_edge(START, "researcher")
researcher_builder.add_conditional_edges("researcher", _researcher_route, {"researcher_tools": "researcher_tools", "compress_research": "compress_research"})
researcher_builder.add_conditional_edges("researcher_tools", _researcher_tools_route, {"researcher": "researcher", "compress_research": "compress_research"})
researcher_builder.add_edge("compress_research", END)
researcher_subgraph = researcher_builder.compile()


def _supervisor_tools_route(state: SupervisorState) -> Literal["supervisor", "__end__"]:
    return (state.get("_supervisor_next") or "supervisor") if state.get("_supervisor_next") != "__end__" else "__end__"


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    iterations = state.get("research_iterations", 0)
    last_msg = supervisor_messages[-1] if supervisor_messages else None

    if iterations > cfg.max_researcher_iterations or not getattr(last_msg, "tool_calls", None):
        return Command(
            goto=END,
            update={
                "notes": _notes_from_tool_messages(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
                "_supervisor_next": "__end__",
            },
        )
    tool_calls = getattr(last_msg, "tool_calls", []) or []
    if any(t.get("name") == "ResearchComplete" for t in tool_calls):
        return Command(
            goto=END,
            update={
                "notes": _notes_from_tool_messages(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
                "_supervisor_next": "__end__",
            },
        )

    all_tool_messages = []
    think_calls = [t for t in tool_calls if t.get("name") == "think_tool"]
    conduct_calls = [t for t in tool_calls if t.get("name") == "ConductResearch"]
    for tc in think_calls:
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {(tc.get('args') or {}).get('reflection', '')}",
            tool_call_id=tc.get("id", ""),
            name="think_tool",
        ))
    allowed = conduct_calls[: cfg.max_concurrent_research_units]
    overflow = conduct_calls[cfg.max_concurrent_research_units:]
    if allowed:
        tasks = [
            researcher_subgraph.ainvoke(
                {"researcher_messages": [HumanMessage(content=t.get("args", {}).get("research_topic", ""))], "research_topic": t.get("args", {}).get("research_topic", "")},
                config,
            )
            for t in allowed
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, tc in enumerate(allowed):
            r = results[i] if i < len(results) else "Error"
            content = (r.get("compressed_research", str(r))) if isinstance(r, dict) else f"Error: {r}"
            all_tool_messages.append(ToolMessage(content=content, tool_call_id=tc.get("id", ""), name="ConductResearch"))
    for tc in overflow:
        all_tool_messages.append(ToolMessage(
            content=f"Skipped: max concurrent research units ({cfg.max_concurrent_research_units}) exceeded.",
            tool_call_id=tc.get("id", ""),
            name="ConductResearch",
        ))

    return Command(goto="supervisor", update={"supervisor_messages": all_tool_messages, "_supervisor_next": "supervisor"})


supervisor_builder.add_node("supervisor_tools", supervisor_tools)
supervisor_builder.add_edge("supervisor", "supervisor_tools")
supervisor_builder.add_conditional_edges("supervisor_tools", _supervisor_tools_route, {"supervisor": "supervisor", "__end__": END})
supervisor_subgraph = supervisor_builder.compile()


async def final_report_generation(state: AgentState, config: RunnableConfig) -> dict:
    cfg = StockDeepResearchConfig.from_runnable_config(config)
    notes = state.get("notes", [])
    findings = "\n\n".join(notes) if notes else "No findings collected."
    from langchain_core.messages import get_buffer_string
    prompt_content = FINAL_REPORT_GENERATION_PROMPT.format(
        research_brief=state.get("research_brief", ""),
        messages=get_buffer_string(state.get("messages", [])),
        findings=findings,
        date=_get_today_str(),
    )
    model = _get_chat_model(cfg.final_report_model, cfg.final_report_model_max_tokens, config)
    try:
        report_msg = await model.ainvoke([HumanMessage(content=prompt_content)])
        report = report_msg.content if hasattr(report_msg, "content") else str(report_msg)
    except Exception as e:
        report = f"Report generation failed: {e}"
    return {
        "final_report": report,
        "notes": {"type": "override", "value": []},
    }


# --- Main graph ---
main_builder = StateGraph(AgentState, input=AgentInputState)
main_builder.add_node("write_research_brief", write_research_brief)
main_builder.add_node("research_supervisor", supervisor_subgraph)
main_builder.add_node("final_report_generation", final_report_generation)
main_builder.add_edge(START, "write_research_brief")
main_builder.add_edge("write_research_brief", "research_supervisor")
main_builder.add_edge("research_supervisor", "final_report_generation")
main_builder.add_edge("final_report_generation", END)

stock_researcher_graph = main_builder.compile()

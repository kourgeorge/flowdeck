"""
ai_engine.agent — LangGraph-based chat agent runtime for FlowDeck.

The agent is built on LangGraph's StateGraph with:
  - LangChain @tool wrappers for all FlowDeck data tools
  - Skill routing (portfolio_health, stock_deep_dive, compare_stocks, portfolio_performance)
  - ReAct tool-calling loop via LangGraph's ToolNode
  - SSE streaming compatible with the existing frontend protocol

Quick start
-----------
from ai_engine.agent import FlowDeckAgent
from ai_engine.llm_provider import get_llm, get_config_from_env

llm = get_llm("deep", get_config_from_env())
agent = FlowDeckAgent(llm=llm)

# Blocking
result = agent.run(messages, user_id=42, db=session, system_prompt="...")

# Streaming (yields SSE strings)
for event in agent.stream(messages, user_id=42, db=session, system_prompt="..."):
    yield event

Domain base classes (tool/skill authors still use these)
---------------------------------------------------------
from ai_engine.agent.tool import BaseTool, ToolSpec, ToolResult, ExecutionContext
from ai_engine.agent.skill import BaseSkill, SkillSpec, SkillResult
"""

# Primary public API — LangGraph agent
from ai_engine.agent.graph import FlowDeckAgent
from ai_engine.agent.state import AgentState
from ai_engine.agent.lc_tools import ALL_LC_TOOLS, get_all_lc_tools

# Domain base classes — still used by tool/skill implementations
from ai_engine.agent.tool import BaseTool, ToolSpec, ToolResult, ExecutionContext
from ai_engine.agent.skill import BaseSkill, SkillSpec, SkillResult

# Legacy registries — still used by skill_node internally
from ai_engine.agent.registry import ToolRegistry, SkillRegistry

__all__ = [
    # LangGraph agent (primary)
    "FlowDeckAgent",
    "AgentState",
    "ALL_LC_TOOLS",
    "get_all_lc_tools",
    # Domain base classes
    "BaseTool",
    "ToolSpec",
    "ToolResult",
    "ExecutionContext",
    "BaseSkill",
    "SkillSpec",
    "SkillResult",
    # Registries
    "ToolRegistry",
    "SkillRegistry",
]



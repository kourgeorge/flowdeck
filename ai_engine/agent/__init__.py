"""
ai_engine.agent — Modular agent runtime with Tools and Skills.

Tools  = atomic, single-step functions exposed directly to the LLM.
Skills = multi-step workflows (recipes) that orchestrate multiple tools
         to accomplish a higher-level goal.

Quick start
-----------
from ai_engine.agent import SkillAgent, ToolRegistry, SkillRegistry
from ai_engine.agent.tools import ALL_TOOLS
from ai_engine.agent.skills import ALL_SKILLS

tool_registry = ToolRegistry()
for t in ALL_TOOLS:
    tool_registry.register(t)

skill_registry = SkillRegistry()
for s in ALL_SKILLS:
    skill_registry.register(s)

agent = SkillAgent(tool_registry=tool_registry, skill_registry=skill_registry, llm=llm)
result = agent.run(messages, ctx)
"""

from ai_engine.agent.tool import BaseTool, ToolSpec, ToolResult, ExecutionContext
from ai_engine.agent.skill import BaseSkill, SkillResult
from ai_engine.agent.registry import ToolRegistry, SkillRegistry
from ai_engine.agent.executor import ToolExecutor, SkillExecutor
from ai_engine.agent.agent import SkillAgent

__all__ = [
    "BaseTool",
    "ToolSpec",
    "ToolResult",
    "ExecutionContext",
    "BaseSkill",
    "SkillResult",
    "ToolRegistry",
    "SkillRegistry",
    "ToolExecutor",
    "SkillExecutor",
    "SkillAgent",
]

# Made with Bob

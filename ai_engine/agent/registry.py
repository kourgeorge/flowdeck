"""
ToolRegistry and SkillRegistry — central registries for tools and skills.

ToolRegistry:
  - Holds all registered BaseTool instances.
  - Supports enable/disable by name.
  - Exports OpenAI function-calling schemas for the LLM.
  - Exports a name→callable map for the agent's tool-dispatch loop.

SkillRegistry:
  - Holds all registered BaseSkill instances.
  - Supports enable/disable by name.
  - Provides intent-matching helpers so the agent can detect when a
    user message should trigger a skill workflow instead of raw tool calls.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from ai_engine.agent.tool import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Central registry for all atomic tools.

    Usage:
        registry = ToolRegistry()
        registry.register(StockQuoteTool())
        registry.disable("web_search")

        schemas = registry.to_openai_schemas()   # for llm.bind_tools()
        fn_map  = registry.to_fn_map()           # for tool dispatch
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool. Overwrites any existing tool with the same name."""
        name = tool.spec.name
        if name in self._tools:
            logger.debug("tool_registry: overwriting existing tool '%s'", name)
        self._tools[name] = tool
        logger.debug("tool_registry: registered '%s'", name)

    def register_many(self, tools: list[BaseTool]) -> None:
        """Register multiple tools at once."""
        for t in tools:
            self.register(t)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[BaseTool]:
        """Return the tool with the given name, or None."""
        return self._tools.get(name)

    def list(self, enabled_only: bool = True) -> list[BaseTool]:
        """Return all (optionally only enabled) tools."""
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    def enable(self, name: str) -> None:
        """Enable a tool by name."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry.")
        tool.enabled = True
        logger.info("tool_registry: enabled '%s'", name)

    def disable(self, name: str) -> None:
        """Disable a tool by name (it stays registered but won't be called)."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry.")
        tool.enabled = False
        logger.info("tool_registry: disabled '%s'", name)

    # ------------------------------------------------------------------
    # LLM integration helpers
    # ------------------------------------------------------------------

    def to_openai_schemas(self, enabled_only: bool = True) -> list[dict]:
        """
        Return OpenAI function-calling schemas for all (enabled) tools.
        Pass the result to ``llm.bind_tools(schemas)``.
        """
        return [t.to_openai_schema() for t in self.list(enabled_only=enabled_only)]

    def to_fn_map(self, enabled_only: bool = True) -> dict[str, Callable]:
        """
        Return a name → execute callable map for tool dispatch.

        The callable signature is ``fn(ctx, **kwargs) -> ToolResult``.
        """
        return {t.name: t.execute for t in self.list(enabled_only=enabled_only)}

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        names = list(self._tools.keys())
        return f"<ToolRegistry tools={names}>"


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """
    Central registry for all multi-step workflow skills.

    Skills are NOT exposed to the LLM as callable functions.
    Instead, the agent uses ``match_intent()`` to detect when a user
    message should trigger a skill, then dispatches to it.

    Usage:
        registry = SkillRegistry()
        registry.register(StockDeepDiveSkill())

        skill = registry.match_intent("give me a deep dive on AAPL")
        if skill:
            result = skill_executor.run(skill, ctx, ticker="AAPL")
    """

    def __init__(self) -> None:
        self._skills: dict[str, object] = {}  # name → BaseSkill

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, skill: object) -> None:
        """Register a skill. Overwrites any existing skill with the same name."""
        name = skill.spec.name  # type: ignore[attr-defined]
        if name in self._skills:
            logger.debug("skill_registry: overwriting existing skill '%s'", name)
        self._skills[name] = skill
        logger.debug("skill_registry: registered '%s'", name)

    def register_many(self, skills: list) -> None:
        """Register multiple skills at once."""
        for s in skills:
            self.register(s)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[object]:
        """Return the skill with the given name, or None."""
        return self._skills.get(name)

    def list(self, enabled_only: bool = True) -> list:
        """Return all (optionally only enabled) skills."""
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if getattr(s, "enabled", True)]
        return skills

    # ------------------------------------------------------------------
    # Enable / Disable
    # ------------------------------------------------------------------

    def enable(self, name: str) -> None:
        """Enable a skill by name."""
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Skill '{name}' not found in registry.")
        skill.enabled = True  # type: ignore[attr-defined]
        logger.info("skill_registry: enabled '%s'", name)

    def disable(self, name: str) -> None:
        """Disable a skill by name."""
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Skill '{name}' not found in registry.")
        skill.enabled = False  # type: ignore[attr-defined]
        logger.info("skill_registry: disabled '%s'", name)

    # ------------------------------------------------------------------
    # Intent matching
    # ------------------------------------------------------------------

    def match_intent(self, user_message: str) -> Optional[object]:
        """
        Skill intent matching is handled by the LLM in the skill_router_node
        (graph.py), which reads skill descriptions from SKILL.md files
        following the agentskills.io standard.

        This method is kept for backward compatibility but always returns None.
        The LangGraph skill_router_node is the authoritative skill selector.
        """
        return None

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        names = list(self._skills.keys())
        return f"<SkillRegistry skills={names}>"

# Made with Bob

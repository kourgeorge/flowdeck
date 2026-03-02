"""
BaseSkill — a multi-step workflow (recipe) that orchestrates multiple tools
to accomplish a higher-level goal.

Skills differ from Tools in that:
  - A Skill runs a *sequence of steps*, each of which may call one or more tools.
  - The Skill controls the flow: it decides what to call next based on prior results.
  - Skills are NOT directly exposed to the LLM as callable functions.
    Instead, the agent detects intent and dispatches to the right skill,
    which then runs its workflow and returns a structured SkillResult.
  - Skills can call other skills (composition).

Example skills:
  - StockDeepDiveSkill: quote → platform reports → news → technicals → synthesize
  - PortfolioHealthSkill: for each subscribed stock → quote + recommendation → summary
  - CompareStocksSkill: fetch fundamentals + quotes for N tickers → comparison table
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ai_engine.agent.tool import ExecutionContext, ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SkillStep — one step in a skill's execution trace
# ---------------------------------------------------------------------------

@dataclass
class SkillStep:
    """
    Records a single step taken during skill execution.

    Used for logging, debugging, and building the final narrative.
    """
    step_num: int
    tool_name: str
    args: dict
    result: ToolResult
    latency_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.result.ok

    def summary(self) -> str:
        status = "✓" if self.ok else "✗"
        return f"[{status}] step {self.step_num}: {self.tool_name}({self.args}) → {self.result.to_str()[:200]}"


# ---------------------------------------------------------------------------
# SkillResult — structured output from a skill workflow
# ---------------------------------------------------------------------------

@dataclass
class SkillResult:
    """
    Structured result returned by a skill after completing its workflow.

    ok=True  → data contains the synthesized output (string or dict).
    ok=False → error contains {code, message}.
    steps    → ordered list of SkillStep records (the execution trace).
    metrics  → optional timing / cost info.
    """
    ok: bool
    data: Any = None
    error: Optional[dict] = None    # {code: str, message: str}
    steps: list[SkillStep] = field(default_factory=list)
    metrics: Optional[dict] = None  # {latency_ms: float, tool_calls: int}

    def to_str(self) -> str:
        """Flatten to a string suitable for feeding back to the LLM."""
        if self.ok:
            return str(self.data) if self.data is not None else ""
        err = self.error or {}
        return f"[Skill error {err.get('code', 'ERR')}] {err.get('message', 'Unknown error')}"

    def trace(self) -> str:
        """Return a human-readable execution trace of all steps."""
        lines = [s.summary() for s in self.steps]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# SkillSpec — metadata descriptor for a skill
# ---------------------------------------------------------------------------

@dataclass
class SkillSpec:
    """
    Metadata that describes a skill to the registry and the agent.

    input_schema describes the arguments the skill accepts when invoked
    programmatically (not via LLM function-calling).
    """
    name: str
    version: str
    description: str
    input_schema: dict          # JSON Schema — describes accepted arguments
    tags: list[str] = field(default_factory=list)
    # Tools this skill is known to use (informational, for registry introspection)
    uses_tools: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BaseSkill — abstract base class for all skills
# ---------------------------------------------------------------------------

class BaseSkill(ABC):
    """
    Abstract base for all multi-step workflow skills.

    Subclasses must:
      1. Define a class-level ``spec: SkillSpec`` attribute.
      2. Implement ``run(ctx, tool_executor, **kwargs) -> SkillResult``.

    The skill receives a ``tool_executor`` so it can call tools safely
    (with timeout + validation) without bypassing the safety layer.

    Skills should:
      - Record each tool call as a SkillStep in the result.
      - Handle partial failures gracefully (continue if one step fails).
      - Return a synthesized SkillResult with a human-readable ``data`` string.
    """

    spec: SkillSpec         # must be set on the class
    enabled: bool = True    # can be toggled by the registry

    @abstractmethod
    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,     # ToolExecutor — avoids circular import
        **kwargs,
    ) -> SkillResult:
        """
        Execute the multi-step workflow.

        Args:
            ctx:           Execution context (user_id, db, budget, logger).
            tool_executor: ToolExecutor instance for safe tool calls.
            **kwargs:      Arguments validated against spec.input_schema.

        Returns:
            SkillResult with ok=True/False and execution trace in steps.
        """
        ...

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    def _step(
        self,
        steps: list[SkillStep],
        step_num: int,
        tool_name: str,
        args: dict,
        result: ToolResult,
        latency_ms: float = 0.0,
    ) -> SkillStep:
        """Helper: create a SkillStep, append to steps list, and return it."""
        s = SkillStep(
            step_num=step_num,
            tool_name=tool_name,
            args=args,
            result=result,
            latency_ms=latency_ms,
        )
        steps.append(s)
        logger.debug("skill=%s %s", self.name, s.summary())
        return s

    def call_tool(
        self,
        tool_executor: Any,
        ctx: ExecutionContext,
        steps: list[SkillStep],
        step_num_ref: list[int],
        tool_name: str,
        **kwargs,
    ) -> ToolResult:
        """
        Look up ``tool_name`` in the executor's registry, run it safely,
        record a SkillStep, and return the ToolResult.

        ``step_num_ref`` is a one-element list used as a mutable counter so
        subclasses don't need a ``nonlocal`` variable.

        Example usage inside a skill's ``run()``::

            step = [0]
            result = self.call_tool(tool_executor, ctx, steps, step, "get_stock_quote", symbol="AAPL")
        """
        import time as _time

        step_num_ref[0] += 1
        n = step_num_ref[0]

        registry = getattr(tool_executor, "tool_registry", None)
        tool = registry.get(tool_name) if registry is not None else None

        if tool is None:
            result = ToolResult(
                ok=False,
                error={"code": "TOOL_NOT_FOUND", "message": f"Tool '{tool_name}' not found."},
            )
            self._step(steps, n, tool_name, kwargs, result)
            return result

        t0 = _time.monotonic()
        result = tool_executor.run(tool, ctx, **kwargs)
        latency_ms = (_time.monotonic() - t0) * 1000
        self._step(steps, n, tool_name, kwargs, result, latency_ms)
        return result

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<Skill {self.spec.name}@{self.spec.version} [{status}]>"

# Made with Bob

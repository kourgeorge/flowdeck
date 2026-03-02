"""
Core data structures for the agent tool system.

A Tool is an atomic, single-step callable exposed to the LLM via
OpenAI function-calling schemas.  The LLM decides when to call a tool;
the ToolExecutor wraps execution with validation, timeout, and error
formatting.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Execution context (per-request state)
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """
    Carries per-request state through the agent runtime.

    Attributes:
        user_id:        Optional authenticated user ID.
        db:             Optional SQLAlchemy session (for user-context tools).
        time_budget_ms: Soft wall-clock budget for the whole agent turn (ms).
        max_tool_calls: Hard cap on total tool invocations per turn.
        memory:         Arbitrary key-value store for intra-turn state.
    """
    user_id: Optional[int] = None
    db: Optional[Any] = None
    time_budget_ms: int = 60_000
    max_tool_calls: int = 10
    memory: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ToolSpec — metadata descriptor for a tool
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    """
    Metadata that describes a tool to the registry and the LLM.

    input_schema is a JSON Schema ``object`` describing the tool's arguments.
    """
    name: str
    description: str
    input_schema: Dict[str, Any]    # JSON Schema "object"
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    side_effects: bool = False      # True if the tool mutates external state


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """
    Structured result returned by every tool execution.

    Attributes:
        ok:      True if the tool succeeded.
        data:    The tool output (string for LLM consumption).
        error:   Error dict with ``code`` and ``message`` keys (if not ok).
        metrics: Optional timing / cost info dict.
    """
    ok: bool
    data: Any = None
    error: Optional[Dict[str, str]] = None
    metrics: Optional[Dict[str, Any]] = None

    def to_str(self) -> str:
        """Return the string the LLM should see as the tool result."""
        if self.ok:
            return str(self.data) if self.data is not None else ""
        code = (self.error or {}).get("code", "TOOL_ERROR")
        msg = (self.error or {}).get("message", "Unknown error")
        return f"[{code}] {msg}"


# ---------------------------------------------------------------------------
# Base tool
# ---------------------------------------------------------------------------

class BaseTool(ABC):
    """
    Abstract base class for all agent tools.

    Subclasses must define a class-level ``spec: ToolSpec`` attribute
    and implement ``execute(ctx, **kwargs) -> ToolResult``.
    """

    spec: ToolSpec          # must be set on the subclass
    enabled: bool = True    # can be toggled by the registry

    @abstractmethod
    def execute(self, ctx: ExecutionContext, **kwargs: Any) -> ToolResult:
        """
        Execute the tool and return a ToolResult.

        Args:
            ctx:      Execution context (user_id, db, budget).
            **kwargs: Tool arguments validated against spec.input_schema.

        Returns:
            ToolResult with ok=True/False.
        """
        ...

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return self.spec.description

    def to_openai_schema(self) -> Dict[str, Any]:
        """Return the OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.spec.name,
                "description": self.spec.description,
                "parameters": self.spec.input_schema,
            },
        }

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<Tool {self.spec.name}@{self.spec.version} [{status}]>"

# Made with Bob

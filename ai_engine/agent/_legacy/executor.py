"""
ToolExecutor and SkillExecutor — safety wrappers for running tools and skills.

ToolExecutor enforces:
  - JSON Schema input validation
  - Timeout (via concurrent.futures thread)
  - Max output payload size (truncation)
  - Deterministic error formatting → always returns ToolResult
  - Structured logging of every call

SkillExecutor wraps ToolExecutor and adds:
  - JSON Schema input validation for skill arguments
  - Timeout for the entire skill workflow
  - Deterministic error formatting → always returns SkillResult
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Optional

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult

logger = logging.getLogger(__name__)

# Max characters allowed in a single tool output before truncation
_MAX_OUTPUT_CHARS = 50_000

# Shared thread pool for timeout enforcement (daemon threads)
_THREAD_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="tool-exec")


def _validate_schema(schema: dict, data: dict) -> Optional[str]:
    """
    Validate ``data`` against ``schema`` using jsonschema if available.
    Returns an error message string on failure, or None if valid.
    """
    try:
        import jsonschema  # type: ignore[import]
        jsonschema.validate(instance=data, schema=schema)
        return None
    except ImportError:
        # jsonschema not installed — skip validation silently
        return None
    except Exception as exc:
        return str(exc)


def _truncate(text: str, max_chars: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated — output exceeded {max_chars} chars]"


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------

class ToolExecutor:
    """
    Safely executes a BaseTool with timeout, input validation, and size limits.

    Usage:
        executor = ToolExecutor()
        result = executor.run(tool, ctx, ticker="AAPL")
    """

    def __init__(self, default_timeout_ms: int = 30_000):
        self.default_timeout_ms = default_timeout_ms

    def run(
        self,
        tool: BaseTool,
        ctx: ExecutionContext,
        **kwargs,
    ) -> ToolResult:
        """
        Execute a tool safely.

        Steps:
          1. Check tool is enabled.
          2. Validate kwargs against tool.spec.input_schema.
          3. Run tool.execute() with timeout.
          4. Truncate oversized output.
          5. Return ToolResult (never raises).
        """
        tool_name = tool.spec.name
        start = time.monotonic()

        # 1. Enabled check
        if not tool.enabled:
            return ToolResult(
                ok=False,
                error={"code": "TOOL_DISABLED", "message": f"Tool '{tool_name}' is disabled."},
            )

        # 2. Input validation
        validation_error = _validate_schema(tool.spec.input_schema, kwargs)
        if validation_error:
            logger.warning("tool=%s input_validation_failed | %s", tool_name, validation_error)
            return ToolResult(
                ok=False,
                error={"code": "INVALID_INPUT", "message": f"Input validation failed: {validation_error}"},
            )

        # 3. Execute with timeout
        timeout_s = ctx.time_budget_ms / 1000.0 if ctx.time_budget_ms else self.default_timeout_ms / 1000.0

        try:
            future = _THREAD_POOL.submit(tool.execute, ctx, **kwargs)
            result: ToolResult = future.result(timeout=timeout_s)
        except FuturesTimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning("tool=%s timeout | elapsed_ms=%.0f", tool_name, elapsed_ms)
            return ToolResult(
                ok=False,
                error={"code": "TIMEOUT", "message": f"Tool '{tool_name}' timed out after {timeout_s:.1f}s."},
                metrics={"latency_ms": elapsed_ms},
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("tool=%s unhandled_exception | error=%s", tool_name, exc)
            return ToolResult(
                ok=False,
                error={"code": "EXECUTION_ERROR", "message": str(exc)},
                metrics={"latency_ms": elapsed_ms},
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # 4. Truncate oversized output and attach metrics
        data = result.data
        if result.ok and data is not None:
            raw = str(data)
            data = _truncate(raw)
            if data != raw:
                logger.debug("tool=%s output_truncated | original_len=%d", tool_name, len(raw))
        result = ToolResult(ok=result.ok, data=data, error=result.error, metrics={"latency_ms": elapsed_ms})

        logger.info(
            "tool=%s ok=%s | latency_ms=%.0f | output_len=%d",
            tool_name,
            result.ok,
            elapsed_ms,
            len(str(result.data or "")),
        )
        return result


# ---------------------------------------------------------------------------
# SkillExecutor
# ---------------------------------------------------------------------------

class SkillExecutor:
    """
    Safely executes a BaseSkill workflow with timeout and input validation.

    Usage:
        skill_executor = SkillExecutor(tool_executor=ToolExecutor())
        result = skill_executor.run(skill, ctx, ticker="AAPL")
    """

    def __init__(
        self,
        tool_executor: Optional[ToolExecutor] = None,
        default_timeout_ms: int = 120_000,  # skills get more time (multi-step)
    ):
        self.tool_executor = tool_executor or ToolExecutor()
        self.default_timeout_ms = default_timeout_ms

    def run(
        self,
        skill: Any,             # BaseSkill — avoids circular import at module level
        ctx: ExecutionContext,
        **kwargs,
    ) -> Any:                   # SkillResult
        """
        Execute a skill workflow safely.

        Steps:
          1. Check skill is enabled.
          2. Validate kwargs against skill.spec.input_schema.
          3. Run skill.run() with timeout.
          4. Return SkillResult (never raises).
        """
        from ai_engine.agent.skill import BaseSkill, SkillResult  # local import

        skill_name = skill.spec.name
        start = time.monotonic()

        # 1. Enabled check
        if not skill.enabled:
            return SkillResult(
                ok=False,
                error={"code": "SKILL_DISABLED", "message": f"Skill '{skill_name}' is disabled."},
            )

        # 2. Input validation
        validation_error = _validate_schema(skill.spec.input_schema, kwargs)
        if validation_error:
            logger.warning("skill=%s input_validation_failed | %s", skill_name, validation_error)
            return SkillResult(
                ok=False,
                error={"code": "INVALID_INPUT", "message": f"Input validation failed: {validation_error}"},
            )

        # 3. Execute with timeout
        timeout_s = self.default_timeout_ms / 1000.0

        try:
            future = _THREAD_POOL.submit(skill.run, ctx, self.tool_executor, **kwargs)
            result = future.result(timeout=timeout_s)
        except FuturesTimeoutError:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning("skill=%s timeout | elapsed_ms=%.0f", skill_name, elapsed_ms)
            return SkillResult(
                ok=False,
                error={"code": "TIMEOUT", "message": f"Skill '{skill_name}' timed out after {timeout_s:.1f}s."},
                metrics={"latency_ms": elapsed_ms},
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.exception("skill=%s unhandled_exception | error=%s", skill_name, exc)
            return SkillResult(
                ok=False,
                error={"code": "EXECUTION_ERROR", "message": str(exc)},
                metrics={"latency_ms": elapsed_ms},
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "skill=%s ok=%s | latency_ms=%.0f | steps=%d",
            skill_name,
            result.ok,
            elapsed_ms,
            len(getattr(result, "steps", [])),
        )
        return result



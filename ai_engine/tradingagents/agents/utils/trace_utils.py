from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def json_safe(value: Any) -> Any:
    """Convert arbitrary values into JSON-safe data for persistence."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def preview_text(value: Any, max_chars: int = 6000) -> str:
    """Render any value into a compact text preview for metadata."""
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(json_safe(value), indent=2, sort_keys=True, default=str)
        except Exception:
            text = str(value)
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def usage_snapshot(usage: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep only stable token/cost fields for persisted step metadata."""
    if not isinstance(usage, dict):
        return None
    out = {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cost_usd": usage.get("cost_usd"),
    }
    if all(v in (None, 0, 0.0) for v in out.values()):
        return None
    return out


_PHASE_ORDER = {
    "analysis": 10,
    "investment_debate": 20,
    "investment_decision": 30,
    "trade_execution": 40,
    "risk_debate": 50,
    "risk_decision": 60,
}


_KIND_ORDER = {
    "llm_decision": 10,
    "tool_call": 20,
    "tool_result": 30,
    "debate_turn": 40,
    "report_synthesis": 50,
}


def _parse_captured_at(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def sort_agent_steps(steps: Any) -> List[Dict[str, Any]]:
    """Return agent steps in a deterministic chronological order."""
    indexed_steps: List[tuple[int, Dict[str, Any]]] = [
        (index, step) for index, step in enumerate(steps or []) if isinstance(step, dict)
    ]

    def _sort_key(item: tuple[int, Dict[str, Any]]) -> tuple[Any, ...]:
        index, step = item
        captured_at = _parse_captured_at(step.get("captured_at"))
        phase_rank = _PHASE_ORDER.get(str(step.get("phase") or ""), 999)
        round_number = step.get("round_number")
        if not isinstance(round_number, int):
            round_number = 10**9
        iteration = step.get("iteration")
        if not isinstance(iteration, int):
            iteration = 10**9
        kind_rank = _KIND_ORDER.get(str(step.get("kind") or ""), 999)
        captured_missing = 1 if captured_at is None else 0
        captured_sort = captured_at or datetime.max.replace(tzinfo=timezone.utc)
        return (
            captured_missing,
            captured_sort,
            phase_rank,
            round_number,
            iteration,
            kind_rank,
            str(step.get("agent") or ""),
            str(step.get("tool_name") or ""),
            index,
        )

    return [step for _, step in sorted(indexed_steps, key=_sort_key)]


def tool_calls_snapshot(tool_calls: Any) -> List[Dict[str, Any]]:
    """Serialize tool call metadata without depending on LangChain internals."""
    out: List[Dict[str, Any]] = []
    if not isinstance(tool_calls, list):
        return out
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            continue
        out.append(
            {
                "id": tool_call.get("id"),
                "name": tool_call.get("name"),
                "args": json_safe(tool_call.get("args") or {}),
            }
        )
    return out


def make_agent_step(
    *,
    agent: str,
    phase: str,
    kind: str,
    report_key: Optional[str] = None,
    iteration: Optional[int] = None,
    round_number: Optional[int] = None,
    status: Optional[str] = None,
    summary: Optional[str] = None,
    message_preview: Any = None,
    output_preview: Any = None,
    observation_preview: Any = None,
    tool_name: Optional[str] = None,
    tool_args: Any = None,
    tool_calls: Any = None,
    usage: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a normalized step record for future visualization."""
    step: Dict[str, Any] = {
        "agent": agent,
        "phase": phase,
        "kind": kind,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    if report_key:
        step["report_key"] = report_key
    if iteration is not None:
        step["iteration"] = iteration
    if round_number is not None:
        step["round_number"] = round_number
    if status:
        step["status"] = status
    if summary:
        step["summary"] = summary
    if message_preview is not None:
        step["message_preview"] = preview_text(message_preview)
    if output_preview is not None:
        step["output_preview"] = preview_text(output_preview)
    if observation_preview is not None:
        step["observation_preview"] = preview_text(observation_preview)
    if tool_name:
        step["tool_name"] = tool_name
    if tool_args is not None:
        step["tool_args"] = json_safe(tool_args)
    tool_calls_data = tool_calls_snapshot(tool_calls)
    if tool_calls_data:
        step["tool_calls"] = tool_calls_data
    usage_data = usage_snapshot(usage)
    if usage_data:
        step["usage"] = usage_data
    if isinstance(extra, dict) and extra:
        step["extra"] = json_safe(extra)
    return step

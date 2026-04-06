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

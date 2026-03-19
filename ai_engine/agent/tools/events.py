"""Events tool for the FlowDeck chat agent."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec


def _ensure_backend_importable() -> None:
    """Add the backend directory to sys.path if it isn't already there."""
    backend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


_EVENTS_SPEC = ToolSpec(
    name="get_events",
    version="1.0",
    description=(
        "Get FlowDeck's event summary for a ticker: unusual price moves, gaps, "
        "52-week breakouts/breakdowns, volume spikes, RSI divergences, upcoming earnings, and "
        "meaningful insider buying/selling. Use when the user asks about important recent events, "
        "stock catalysts, notable technical signals, or what stands out right now for a ticker."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA, NVDA",
            }
        },
        "required": ["ticker"],
    },
    tags=["events", "technical", "fundamental"],
)


class EventsTool(BaseTool):
    spec = _EVENTS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            result = _fetch_events(ticker)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _fetch_events(ticker: str) -> str:
    from ai_engine.tradingagents.datasources.info_service_client import (
        get_events,
        is_configured,
    )

    ticker_upper = ticker.strip().upper()
    payload: dict[str, Any] | None = None

    _ensure_backend_importable()
    try:
        from data_layer import get_data_gateway
        from processing import get_ticker_event_summary

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary = get_ticker_event_summary(
            get_data_gateway(),
            ticker_upper,
            as_of_date=today,
        )
        payload = summary.model_dump(mode="json")
    except (ImportError, RuntimeError):
        if is_configured():
            payload = get_events(ticker_upper)
        else:
            return (
                "Events unavailable: set INFO_SERVICE_URL to your FlowDeck backend, "
                "or run the chat agent from within the backend process."
            )

    return _format_events_payload(ticker_upper, payload or {})


def _format_events_payload(ticker: str, payload: dict[str, Any]) -> str:
    error = str(payload.get("error") or "").strip()
    event_score = payload.get("event_score", 0.0)
    event_count = payload.get("event_count", 0)
    dominant_events = payload.get("dominant_events") or []
    events = payload.get("events") or []

    lines = [f"# Events for {ticker}"]
    if error:
        lines.append(f"Warning: {error}")
        lines.append("")

    lines.append(f"Event score: {_format_scalar(event_score)}")
    lines.append(f"Event count: {_format_scalar(event_count)}")
    lines.append(
        "Dominant events: "
        + (", ".join(str(item) for item in dominant_events[:8]) if dominant_events else "none")
    )
    lines.append("")

    if not events:
        lines.append(f"No active events were detected for {ticker}.")
        return "\n".join(lines)

    lines.append("## Active events")
    for idx, event in enumerate(events[:12], 1):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type") or "unknown")
        domain = str(event.get("domain") or "unknown")
        strength = str(event.get("strength") or "unknown")
        detected_on = str(event.get("detected_on") or "unknown")
        description = str(event.get("description") or "").strip()
        metric_value = event.get("metric_value")
        threshold_value = event.get("threshold_value")
        metadata = event.get("metadata") or {}

        lines.append(f"{idx}. {event_type} | domain={domain} | strength={strength} | detected_on={detected_on}")
        if description:
            lines.append(f"   Description: {description}")
        if metric_value is not None or threshold_value is not None:
            lines.append(
                "   Trigger: "
                f"metric={_format_scalar(metric_value)}, threshold={_format_scalar(threshold_value)}"
            )
        metadata_summary = _summarize_metadata(metadata)
        if metadata_summary:
            lines.append(f"   Metadata: {metadata_summary}")

    remaining = len(events) - 12
    if remaining > 0:
        lines.append(f"... and {remaining} more event(s).")

    return "\n".join(lines)


def _summarize_metadata(metadata: Any) -> str:
    if not isinstance(metadata, dict) or not metadata:
        return ""
    parts: list[str] = []
    for key, value in list(metadata.items())[:5]:
        parts.append(f"{key}={_format_scalar(value)}")
    return ", ".join(parts)


def _format_scalar(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:5]) if value else "[]"
    return str(value)

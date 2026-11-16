"""Events tool for the FlowDeck chat agent."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# The chat agent and the trading agents must render events identically, so the
# formatter lives once in the trading-agents tools. Imported at module level
# because backend/tests/test_agent_event_tools.py imports it from here.
from ai_engine.tradingagents.agents.utils.events_tools import _format_events_payload


def _ensure_backend_importable() -> None:
    """Add the backend directory to sys.path so `data_layer` can be imported."""
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
        # data_layer imports backend.processing, which plugs the backend cache into
        # ai_engine.processing (configure_event_cache), so summaries here stay cached.
        from data_layer import get_data_gateway

        from ai_engine.processing import get_ticker_event_summary

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

    payload = payload or {}
    if payload.get("available") is False or ("event_score" in payload and payload.get("event_score") is None):
        # The shared formatter would follow the warning with "No active events were
        # detected", which reads as a quiet ticker. Say plainly that nothing was checked.
        reason = str(payload.get("error") or "price history could not be loaded").strip()
        return f"Events unavailable for {ticker_upper}: {reason}. No event score was computed; do not read this as a quiet ticker."
    return _format_events_payload(ticker_upper, payload)


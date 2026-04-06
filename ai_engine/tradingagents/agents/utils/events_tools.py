from typing import Annotated, Any

from langchain_core.tools import tool

from ...datasources.info_service_client import (
    get_events as get_events_via_service,
    require_info_service,
)


def fetch_events_report(ticker: str, lookback_days: int = 10) -> str:
    """Fetch and format deterministic event context for a ticker."""
    require_info_service()
    ticker_upper = (ticker or "").strip().upper()
    payload = get_events_via_service(ticker_upper, lookback_days=lookback_days) or {}

    if not payload:
        return (
            f"# Events for {ticker_upper}\n"
            "No deterministic event data was returned by the backend."
        )

    return _format_events_payload(ticker_upper, payload)


@tool
def get_events(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL, MSFT, NVDA"],
    lookback_days: Annotated[int, "Trailing number of days to scan for price/technical events"] = 10,
) -> str:
    """
    Retrieve FlowDeck's deterministic event summary for a ticker.
    Includes unusual price moves, gaps, breakouts, volume spikes, volatility
    shifts, upcoming earnings, and meaningful insider activity.
    """
    return fetch_events_report(ticker, lookback_days=lookback_days)


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

        lines.append(
            f"{idx}. {event_type} | domain={domain} | strength={strength} | detected_on={detected_on}"
        )
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

"""Fallback markdown when the LLM writer is unavailable (same shape as UI expects)."""

from __future__ import annotations

from typing import Any, Mapping

IMPORTANT_EVENT_LABELS: dict[str, str] = {
    "price_spike_up": "Price spike up",
    "price_spike_down": "Price spike down",
    "price_gap_up": "Gap up",
    "price_gap_down": "Gap down",
    "volatility_expansion": "Volatility expansion",
    "volatility_compression": "Volatility compression",
    "moving_average_cross": "Moving average cross",
    "new_52w_high": "New 52-week high",
    "new_52w_low": "New 52-week low",
    "volume_spike": "Volume spike",
    "earnings_upcoming": "Upcoming earnings",
    "insider_buying": "Insider buying",
    "insider_selling": "Insider selling",
    "rsi_bullish_divergence": "RSI bullish divergence",
    "rsi_bearish_divergence": "RSI bearish divergence",
}


def _format_event_label(event_type: str) -> str:
    return IMPORTANT_EVENT_LABELS.get(event_type, event_type.replace("_", " "))


def _cluster_summary(interest_cluster: Mapping[str, Any]) -> str:
    sectors = interest_cluster.get("sectors")
    industries = interest_cluster.get("industries")
    parts: list[str] = []
    if isinstance(sectors, list) and sectors:
        parts.append("Sectors: " + ", ".join(str(s) for s in sectors[:5]))
    if isinstance(industries, list) and industries:
        parts.append("Industries: " + ", ".join(str(i) for i in industries[:5]))
    return " · ".join(parts) or (
        "No sector/industry cluster matched (subscribe to more tickers or try again later)."
    )


def _format_event_bullet(e: Mapping[str, Any]) -> str:
    desc_raw = e.get("description")
    desc = desc_raw.strip() if isinstance(desc_raw, str) and desc_raw.strip() else None
    et = e.get("event_type")
    label = _format_event_label(str(et)) if et else "Signal"
    main = desc if desc else label
    meta: list[str] = []
    if e.get("strength"):
        meta.append(str(e["strength"]))
    if e.get("detected_on"):
        meta.append(str(e["detected_on"]))
    if meta:
        return f"{main} _({' · '.join(meta)})_"
    return main


def stocks_discovery_payload_to_markdown(
    *,
    digest_date: str,
    span_type: str,
    interest_cluster: Mapping[str, Any],
    discovered_tickers: list[str],
    discovered_ticker_events: Mapping[str, Any],
    discovered_ticker_info: Mapping[str, Any],
) -> str:
    span_word = "Weekly" if span_type == "weekly" else "Daily"
    lines: list[str] = [
        "# Stocks discovery report",
        "",
        f"**{span_word}** · {digest_date}",
        "",
        f"**Interest cluster:** {_cluster_summary(interest_cluster)}",
        "",
        "These symbols are **not** in your portfolio. They appeared in liquid market movers and matched "
        "your sector/industry cluster, then ranked highly on FlowDeck's deterministic event signals "
        "(price action, volume, calendar, insiders, RSI, etc.).",
        "",
    ]
    if not discovered_tickers:
        lines.append("_No tickers met the discovery threshold for this run._")
        return "\n".join(lines)

    for t in discovered_tickers:
        info_raw = discovered_ticker_info.get(t, {})
        info: Mapping[str, Any] = info_raw if isinstance(info_raw, dict) else {}
        sector = str(info.get("sector") or "—")
        ind = info.get("industry")
        industry = str(ind) if isinstance(ind, str) and ind != "N/A" else None
        ev_raw = discovered_ticker_events.get(t)
        ev: Mapping[str, Any] = ev_raw if isinstance(ev_raw, dict) else {}
        score = ev.get("event_score")
        score_s = f"{float(score):.2f}" if isinstance(score, (int, float)) else None
        dom_raw = ev.get("dominant_events")
        dominant = [str(x) for x in dom_raw] if isinstance(dom_raw, list) else []

        lines.append(f"## {t}")
        lines.append("")
        ind_part = f" · **Industry:** {industry}" if industry else ""
        lines.append(f"- **Sector:** {sector}{ind_part}")
        if score_s:
            lines.append(
                "- **Event score:** "
                + score_s
                + " _(blend of detected signals; higher means more notable activity in this scan)_"
            )
        if dominant:
            lines.append(
                "- **Top signal types:** " + ", ".join(_format_event_label(x) for x in dominant)
            )
        lines.append("")
        events_raw = ev.get("events")
        events = events_raw if isinstance(events_raw, list) else []
        if events:
            lines.append("**What the scanner flagged:**")
            lines.append("")
            max_events = 12
            for e in events[:max_events]:
                if isinstance(e, dict):
                    lines.append(f"- {_format_event_bullet(e)}")
            if len(events) > max_events:
                lines.append(f"- _…and {len(events) - max_events} more signal(s)._")
            lines.append("")
        else:
            lines.append("_No per-event detail was returned for this ticker (score only)._")
            lines.append("")

    return "\n".join(lines)

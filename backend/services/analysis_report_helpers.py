"""Report-building helpers shared by AnalysisService and run_analysis_standalone.

These used to live twice: once inside AnalysisService's run closure and once as a hand
copy in the standalone runner. The copies drifted -- the standalone one never gained the
event signal, so a manual standalone run saved a trader_investment_plan without
event_score and the event monitor then skipped that ticker as "no baseline". Keeping a
single copy here means both paths save the same report metadata.

Per-run values that the closures used to capture (analysis_run_id, ticker, the takeaway
cache) are plain parameters, so callers bind them with functools.partial.
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from ai_engine.tradingagents.agents.utils.trace_utils import sort_agent_steps

logger = logging.getLogger(__name__)


def progress_log(msg: str) -> None:
    """Print a progress line to stderr with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Progress]:\t {ts} - {msg}", file=sys.stderr, flush=True)


def extract_content_string(content) -> str:
    """Flatten LangChain message content (str or list of content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    text_parts.append(f"[Tool: {item.get('name', 'unknown')}]")
            else:
                text_parts.append(str(item))
        return " ".join(text_parts)
    return str(content)


def normalize_takeaway_list(val) -> list:
    """Non-empty strings only, max 5 (from graph structured fields or similar)."""
    if not val:
        return []
    if not isinstance(val, (list, tuple)):
        return []
    return [str(x).strip() for x in val if x and str(x).strip()][:5]


# Saved report type -> AgentState key produced by the graph (avoid a second LLM for takeaways).
REPORT_TO_STATE_TAKEAWAYS_KEY = {
    "market_report": "market_key_takeaways",
    "sentiment_report": "sentiment_key_takeaways",
    "fundamentals_report": "fundamentals_key_takeaways",
    "technical_report": "technical_key_takeaways",
    "sec_report": "sec_key_takeaways",
    "valuation_report": "valuation_key_takeaways",
    "investment_plan": "investment_plan_key_takeaways",
    "trader_investment_plan": "trader_key_takeaways",
    "final_trade_decision": "final_report_key_takeaways",
}


def build_report_json(
    content,
    score,
    score_label,
    key_takeaways_list,
    *,
    analysis_date,
    generated_at,
    models_used,
    **extra,
) -> Dict[str, Any]:
    meta = {"score_label": score_label or "Score", "analysis_date": analysis_date, "generated_at": generated_at, "models_used": models_used}
    if score is not None:
        meta["score"] = score
    if key_takeaways_list:
        meta["key_takeaways"] = [str(t or "").strip() for t in key_takeaways_list[:5] if t]
    meta.update({k: v for k, v in extra.items() if v is not None})
    return {"metadata": meta, "content": content or ""}


def get_analysis_quote_meta(ticker: str) -> Dict[str, Any]:
    try:
        from data_layer import get_data_gateway
        quote = get_data_gateway().get_quote(ticker)
    except Exception:
        return {}
    if not isinstance(quote, dict):
        return {}
    current_price = quote.get("current_price")
    currency = quote.get("currency")
    meta: Dict[str, Any] = {}
    if isinstance(current_price, (int, float)):
        meta["current_price"] = float(current_price)
    if isinstance(currency, str) and currency.strip():
        meta["currency"] = currency.strip().upper()
    return meta


def get_analysis_event_meta(ticker: str, analysis_date: str) -> Dict[str, Any]:
    """Deterministic event signal as of this analysis, for the event monitor.

    Recorded now because it cannot be recomputed later: extract_price_technical_events
    windows its *events* by end_date but derives prefix stats and 52-week extremes from
    every bar it is handed, so replaying a past date leaks the future.
    """
    try:
        from data_layer import get_data_gateway
        from processing import get_ticker_event_summary
        summary = get_ticker_event_summary(get_data_gateway(), ticker, as_of_date=analysis_date)
    except Exception as e:
        logger.warning("Failed to read event signal for %s: %s", ticker, e)
        return {}
    if summary.event_score is None:
        # Price history couldn't be loaded. Stamping 0.0 here would become the event
        # monitor's baseline and make the next real score look like a spike, so record
        # nothing and let the monitor skip this ticker as "no baseline".
        logger.warning("Event signal unavailable for %s: %s", ticker, getattr(summary, "error", None))
        return {}
    return {
        "event_score": float(summary.event_score),
        "dominant_events": list(summary.dominant_events or []),
    }


def get_or_extract_takeaways(
    report_takeaways: Dict[str, list],
    report_key,
    content,
    chunk=None,
    *,
    analysis_run_id,
) -> list:
    """Use structured takeaways from graph state only; no content scraping or extra LLM.

    ``report_takeaways`` is the per-run cache, filled in place.
    """
    if report_key in report_takeaways:
        logger.info(
            "Key takeaways extraction skipped (cached) analysis_run_id=%s report_type=%s",
            analysis_run_id, report_key,
        )
        return report_takeaways[report_key]
    state_key = REPORT_TO_STATE_TAKEAWAYS_KEY.get(report_key)
    if chunk is not None and state_key:
        preferred = normalize_takeaway_list(chunk.get(state_key))
        if preferred:
            report_takeaways[report_key] = preferred
            logger.info(
                "Key takeaways from graph state analysis_run_id=%s report_type=%s items=%s",
                analysis_run_id, report_key, len(preferred),
            )
            return preferred
    takeaways: list = []
    report_takeaways[report_key] = takeaways
    return takeaways


def get_report_resources(
    chunk: Optional[Dict[str, Any]],
    report_key: str,
) -> List[Dict[str, Any]]:
    if not isinstance(chunk, dict):
        return []
    by_report = chunk.get("report_resources_by_report")
    if isinstance(by_report, dict):
        specific = by_report.get(report_key)
        if isinstance(specific, list):
            return specific
    resources = chunk.get("report_resources")
    return resources if isinstance(resources, list) else []


def get_report_agent_steps(
    chunk: Optional[Dict[str, Any]],
    report_key: str,
) -> List[Dict[str, Any]]:
    if not isinstance(chunk, dict):
        return []
    by_report = chunk.get("report_steps_by_report")
    if isinstance(by_report, dict):
        specific = by_report.get(report_key)
        if isinstance(specific, list):
            return sort_agent_steps(specific)
    return []

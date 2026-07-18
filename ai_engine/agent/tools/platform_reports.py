"""
PlatformReportsTool — fetch FlowDeck AI analysis reports for a ticker.
HistoricalReportDatesTool — list available historical report dates for a ticker.
"""

from __future__ import annotations

import os
import sys

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec


def _ensure_backend_importable() -> None:
    """Add the backend directory to sys.path if it isn't already there."""
    backend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend")
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

# ---------------------------------------------------------------------------
# Canonical report keys and aliases (mirrors chat_service.py)
# ---------------------------------------------------------------------------

_REPORT_LABELS = {
    "market_report": "Market Analysis",
    "fundamentals_report": "Fundamentals Analysis",
    "technical_report": "Technical Analysis",
    "sentiment_report": "News & Sentiment Analysis",
    "sec_report": "SEC Analysis",
    "valuation_report": "Valuation Analysis",
    "investment_plan": "Investment Plan",
    "trader_investment_plan": "Trader Plan",
    "final_trade_decision": "Final Decision",
}

_REPORT_ALIASES: dict[str, str] = {
    "market": "market_report",
    "fundamentals": "fundamentals_report",
    "fundamental": "fundamentals_report",
    "technical": "technical_report",
    "news": "sentiment_report",
    "sentiment": "sentiment_report",
    "social": "sentiment_report",
    "sec": "sec_report",
    "valuation": "valuation_report",
    "investment": "investment_plan",
    "plan": "investment_plan",
    "research": "investment_plan",
    "recommendation": "investment_plan",
    "trader": "trader_investment_plan",
    "trader_plan": "trader_investment_plan",
    # Historical alias — final_trade_decision is no longer produced but old runs still have it.
    "final": "final_trade_decision",
    "decision": "final_trade_decision",
}


# ---------------------------------------------------------------------------
# PlatformReportsTool
# ---------------------------------------------------------------------------

_PLATFORM_REPORTS_SPEC = ToolSpec(
    name="get_platform_reports",
    version="1.0",
    description=(
        "ALWAYS call this first when the user asks about a stock's analysis, recommendation, outlook, "
        "investment thesis, bull/bear case, risk assessment, or any AI-generated insight. "
        "Retrieves FlowDeck's proprietary AI analysis reports from the platform database for a given ticker. "
        "Without report_type: returns a summary of ALL reports — recommendation, return scenarios, "
        "scores, and key takeaways for each report (no full text). "
        "With report_type: returns the full content of that specific report. "
        "Available reports: Investment Plan (Bull/Bear/Neutral researcher debate + the authoritative "
        "BUY/SELL/HOLD recommendation), Trader Plan, Market Analysis, "
        "Fundamentals Analysis, Technical Analysis, News & Sentiment Analysis, SEC/Regulatory Analysis, "
        "and Valuation Analysis. "
        "Use report_type when the user asks to 'read', 'show', 'summarize', or 'deep dive' into a specific report. "
        "By default returns the LATEST report. Use the 'date' parameter to access historical reports — "
        "first call get_historical_report_dates to discover available dates, then pass the desired date here."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA, NVDA",
            },
            "report_type": {
                "type": "string",
                "description": (
                    "Optional. Fetch only a specific report instead of all reports. "
                    "Accepted values: 'investment_plan' (or 'investment'/'plan'/'research'/'recommendation'), "
                    "'trader_investment_plan' (or 'trader'/'trader_plan'), "
                    "'final_trade_decision' (or 'final'/'decision' — historical runs only), "
                    "'market_report' (or 'market'), "
                    "'fundamentals_report' (or 'fundamentals'/'fundamental'), "
                    "'technical_report' (or 'technical'), "
                    "'sentiment_report' (or 'news'/'sentiment'/'social'), "
                    "'sec_report' (or 'sec'). "
                    "'valuation_report' (or 'valuation'). "
                    "Omit or leave null to fetch all available reports."
                ),
            },
            "date": {
                "type": "string",
                "description": (
                    "Optional. Fetch reports from a specific historical analysis date instead of the latest. "
                    "Accepts YYYY-MM-DD (e.g. '2025-01-15') or analysis_run_id as string. "
                    "Use get_historical_report_dates first to discover available dates for a ticker. "
                    "Omit or leave null to fetch the most recent reports."
                ),
            },
        },
        "required": ["ticker"],
    },
    tags=["reports", "analysis", "ai"],
)


class PlatformReportsTool(BaseTool):
    spec = _PLATFORM_REPORTS_SPEC

    def execute(
        self,
        ctx: ExecutionContext,
        *,
        ticker: str,
        report_type: str | None = None,
        date: str | None = None,
        **_,
    ) -> ToolResult:
        try:
            result = _fetch_platform_reports(ticker, report_type, date)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _fetch_platform_reports(
    ticker: str,
    report_type: str | None = None,
    date: str | None = None,
) -> str:
    from ai_engine.tradingagents.datasources.info_service_client import (
        get_reports,
        get_report_dates,
        is_configured,
    )

    ticker = ticker.strip().upper()

    # Resolve report_type alias
    canonical_type: str | None = None
    if report_type:
        rt = report_type.strip().lower()
        canonical_type = _REPORT_ALIASES.get(rt, rt)
        if canonical_type not in _REPORT_LABELS:
            valid = ", ".join(sorted(_REPORT_LABELS.keys()))
            return (
                f"Unknown report_type '{report_type}'. "
                f"Valid values: {valid}. "
                f"Also accepted aliases: {', '.join(sorted(_REPORT_ALIASES.keys()))}."
            )

    # Prefer in-process when backend is available (e.g. chat served by backend).
    # HTTP path requires auth; in-process does not. External agents use INFO_SERVICE_URL + Bearer token.
    reports_with_scores: dict = {}
    date_display = ""

    _ensure_backend_importable()
    try:
        from data_layer import get_data_gateway
        gw = get_data_gateway()
        analysis_run_id: int | None = None
        if date:
            date = date.strip()
            resolved = gw.get_analysis_run_for_date(ticker, date)
            if not resolved:
                all_dates = gw.list_report_dates(ticker)
                return (
                    f"No reports found for {ticker} on date '{date}'. "
                    f"Available dates: {', '.join(all_dates[:10])}."
                )
            analysis_run_id, date_display = resolved
        if analysis_run_id is None:
            latest = gw.get_latest_execution_for_ticker(ticker)
            if not latest:
                return (
                    f"No AI analysis reports found for **{ticker}** on FlowDeck. "
                    f"Reports are generated when a full analysis is run for this ticker."
                )
            analysis_run_id, date_display = latest
        reports_with_scores = gw.get_reports_with_scores(analysis_run_id)
    except (ImportError, RuntimeError):
        # Backend not available; use HTTP (requires INFO_SERVICE_URL and Bearer auth for reports)
        if not is_configured():
            return (
                "Platform reports unavailable: set INFO_SERVICE_URL to your FlowDeck backend, "
                "or run the chat agent from within the backend process."
            )
        data = get_reports(ticker, date=date.strip() if date else None)
        if not data:
            if date:
                all_dates = get_report_dates(ticker)
                return (
                    f"No reports found for {ticker} on date '{date}'. "
                    f"Available dates: {', '.join(all_dates[:10])}."
                )
            return (
                f"No AI analysis reports found for **{ticker}** on FlowDeck. "
                f"Reports are generated when a full analysis is run for this ticker."
            )
        reports_with_scores = data.get("reports") or {}
        date_display = str(data.get("report_date") or "")

    # --- Fetch specific report ---
    if canonical_type:
        content = (reports_with_scores.get(canonical_type) or {}).get("content") or ""
        if not content:
            return (
                f"The '{_REPORT_LABELS.get(canonical_type, canonical_type)}' report "
                f"is not available for {ticker} (run: {date_display})."
            )
        label = _REPORT_LABELS.get(canonical_type, canonical_type)
        return f"# FlowDeck {label} for {ticker}\n*(Analysis date: {date_display})*\n\n{content}"

    # --- Fetch all reports summary ---
    reports = reports_with_scores
    if not reports:
        return f"No report data found for {ticker} (run: {date_display})."

    lines = [f"# FlowDeck AI Analysis Summary for {ticker}", f"*(Analysis date: {date_display})*", ""]

    # Recommendation first. The Research Manager (investment_plan) is now the authoritative
    # source of the BUY/SELL/HOLD recommendation; final_trade_decision is kept as a fallback
    # for historical runs produced before the Research/Risk report merge.
    inv = reports.get("investment_plan") or {}
    ftd = reports.get("final_trade_decision") or {}
    rec_source = inv if inv.get("recommendation") else ftd
    if rec_source:
        rec = rec_source.get("recommendation", "N/A")
        conf = rec_source.get("confidence")
        conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
        lines.append(f"## 🎯 Recommendation: **{rec}**{conf_str}")
        # Show key takeaways if available
        kt = rec_source.get("key_takeaways")
        if kt and isinstance(kt, list):
            for item in kt[:3]:  # Show top 3 takeaways
                lines.append(f"- {item}")
        lines.append("")

    # Investment plan return scenarios
    if inv:
        exp = inv.get("expected_return_pct")
        bear = inv.get("bear_case_return_pct")
        bull = inv.get("bull_case_return_pct")
        if any(v is not None for v in [exp, bear, bull]):
            parts = []
            if exp is not None:
                parts.append(f"Expected: **{exp:+.1f}%**")
            if bear is not None:
                parts.append(f"Bear: **{bear:+.1f}%**")
            if bull is not None:
                parts.append(f"Bull: **{bull:+.1f}%**")
            lines.append("## 📊 Return Scenarios")
            lines.append(" | ".join(parts))
            lines.append("")

    # Trader Plan and TPS — include full trading plan narrative and structured TPS so the agent cites them
    tip = reports.get("trader_investment_plan") or {}
    if tip:
        lines.append("## 📋 Trader Plan (recommended trading plan)")
        content = tip.get("content") or ""
        if content.strip():
            lines.append(content.strip())
        else:
            kt = tip.get("key_takeaways")
            if kt and isinstance(kt, list):
                for item in kt[:8]:
                    lines.append(f"- {item}")
        tps = tip.get("tps_plan")
        if tps and str(tps).strip():
            lines.append("")
            lines.append("### TPS — structured entry, stop-loss, and take-profit levels")
            lines.append("Use these levels when answering questions about entry, exit, stop-loss, or take-profit.")
            lines.append("```")
            lines.append(str(tps).strip())
            lines.append("```")
        lines.append("")

    # Per-report summaries (skip trader_investment_plan — already covered above)
    for key, label in _REPORT_LABELS.items():
        if key in ("final_trade_decision", "investment_plan", "trader_investment_plan"):
            continue
        rpt = reports.get(key) or {}
        if not rpt:
            continue
        lines.append(f"## {label}")
        score = rpt.get("score")
        if score is not None:
            lines.append(f"Score: {score}/10")
        summary = rpt.get("summary") or rpt.get("key_takeaways")
        if summary:
            if isinstance(summary, list):
                for item in summary[:5]:
                    lines.append(f"- {item}")
            else:
                lines.append(str(summary)[:500])
        lines.append("")

    lines.append(
        f"*To read the full text of any report, call get_platform_reports with "
        f"report_type='<report_name>' (e.g. 'final_trade_decision', 'technical_report').*"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HistoricalReportDatesTool
# ---------------------------------------------------------------------------

_HISTORICAL_DATES_SPEC = ToolSpec(
    name="get_historical_report_dates",
    version="1.0",
    description=(
        "List all historical AI analysis report dates available for a ticker on the FlowDeck platform. "
        "Returns a chronological list of run dates (newest first) with the report types available for each date. "
        "Use this tool when the user asks about: past analyses, historical recommendations, how the outlook "
        "has changed over time, previous reports, or any question involving a specific past date. "
        "After calling this, use get_platform_reports with the 'date' parameter to fetch reports from a specific date."
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
    tags=["reports", "history", "ai"],
)


class HistoricalReportDatesTool(BaseTool):
    spec = _HISTORICAL_DATES_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            result = _fetch_historical_dates(ticker)
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _fetch_historical_dates(ticker: str) -> str:
    from ai_engine.tradingagents.datasources.info_service_client import (
        get_report_dates,
        is_configured,
    )

    ticker = ticker.strip().upper()
    dates: list = []

    _ensure_backend_importable()
    try:
        from data_layer import get_data_gateway
        gw = get_data_gateway()
        dates = gw.list_report_dates(ticker)
    except (ImportError, RuntimeError):
        if is_configured():
            dates = get_report_dates(ticker)
        else:
            return (
                "Platform reports unavailable: set INFO_SERVICE_URL to your FlowDeck backend, "
                "or run the chat agent from within the backend process."
            )

    if not dates:
        return f"No historical reports found for {ticker} on FlowDeck."

    lines = [
        f"# Historical Report Dates for {ticker}",
        f"Found {len(dates)} analysis run(s) — newest first:",
        "",
    ]
    for i, d in enumerate(dates[:20], 1):
        lines.append(f"{i}. `{d}`")

    if len(dates) > 20:
        lines.append(f"... and {len(dates) - 20} more.")

    lines.append("")
    lines.append(
        "To fetch reports from a specific date, call get_platform_reports with "
        "the date parameter set to one of the dates above (YYYY-MM-DD)."
    )
    return "\n".join(lines)


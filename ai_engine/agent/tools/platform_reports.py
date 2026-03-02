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
    "news_report": "News Analysis",
    "sec_report": "SEC Analysis",
    "investment_plan": "Investment Plan",
    "trader_investment_plan": "Trader Plan",
    "final_trade_decision": "Final Decision",
}

_REPORT_ALIASES: dict[str, str] = {
    "market": "market_report",
    "fundamentals": "fundamentals_report",
    "fundamental": "fundamentals_report",
    "technical": "technical_report",
    "news": "news_report",
    "sec": "sec_report",
    "investment": "investment_plan",
    "plan": "investment_plan",
    "trader": "trader_investment_plan",
    "trader_plan": "trader_investment_plan",
    "final": "final_trade_decision",
    "decision": "final_trade_decision",
    "recommendation": "final_trade_decision",
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
        "Available reports: Final Trade Decision (risk-adjusted recommendation), "
        "Investment Plan (bull vs bear researcher debate), Trader Plan, Market Analysis, "
        "Fundamentals Analysis, Technical Analysis, News Analysis, SEC/Regulatory Analysis. "
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
                    "Accepted values: 'final_trade_decision' (or 'final'/'decision'/'recommendation'), "
                    "'investment_plan' (or 'investment'/'plan'), "
                    "'trader_investment_plan' (or 'trader'/'trader_plan'), "
                    "'market_report' (or 'market'), "
                    "'fundamentals_report' (or 'fundamentals'/'fundamental'), "
                    "'technical_report' (or 'technical'), "
                    "'news_report' (or 'news'), "
                    "'sec_report' (or 'sec'). "
                    "Omit or leave null to fetch all available reports."
                ),
            },
            "date": {
                "type": "string",
                "description": (
                    "Optional. Fetch reports from a specific historical analysis date instead of the latest. "
                    "Accepts YYYY-MM-DD (e.g. '2025-01-15') or a full run_id (e.g. '2025-01-15_10-30-00'). "
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
    _ensure_backend_importable()
    try:
        from services.report_service import ReportService
    except ImportError:
        return f"Platform reports unavailable: backend not importable."

    ticker = ticker.strip().upper()
    svc = ReportService()

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

    # Resolve date / run_id
    run_id: str | None = None
    if date:
        date = date.strip()
        all_dates = svc.list_report_dates(ticker)
        if not all_dates:
            return f"No reports found for {ticker}."
        # Exact run_id match
        if date in all_dates:
            run_id = date
        else:
            # Prefix match on YYYY-MM-DD
            matches = [d for d in all_dates if d.startswith(date)]
            if not matches:
                return (
                    f"No reports found for {ticker} on date '{date}'. "
                    f"Available dates: {', '.join(all_dates[:10])}."
                )
            run_id = matches[0]  # most recent match

    # Fetch latest date if no run_id specified
    if run_id is None:
        run_id = svc.get_latest_report_date(ticker)
        if run_id is None:
            return (
                f"No AI analysis reports found for **{ticker}** on FlowDeck. "
                f"Reports are generated when a full analysis is run for this ticker."
            )

    # --- Fetch specific report ---
    if canonical_type:
        content = svc.get_report_content(ticker, run_id, canonical_type)
        if not content:
            return (
                f"The '{_REPORT_LABELS.get(canonical_type, canonical_type)}' report "
                f"is not available for {ticker} (run: {run_id})."
            )
        label = _REPORT_LABELS.get(canonical_type, canonical_type)
        return f"# FlowDeck {label} for {ticker}\n*(Analysis date: {run_id})*\n\n{content}"

    # --- Fetch all reports summary ---
    reports = svc.get_reports_with_scores(ticker, run_id)
    if not reports:
        return f"No report data found for {ticker} (run: {run_id})."

    lines = [f"# FlowDeck AI Analysis Summary for {ticker}", f"*(Analysis date: {run_id})*", ""]

    # Final trade decision first
    ftd = reports.get("final_trade_decision") or {}
    if ftd:
        rec = ftd.get("recommendation", "N/A")
        conf = ftd.get("confidence")
        conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
        lines.append(f"## 🎯 Final Trade Decision: **{rec}**{conf_str}")
        if ftd.get("summary"):
            lines.append(ftd["summary"])
        lines.append("")

    # Investment plan return scenarios
    inv = reports.get("investment_plan") or {}
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

    # Per-report summaries
    for key, label in _REPORT_LABELS.items():
        if key in ("final_trade_decision", "investment_plan"):
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
    _ensure_backend_importable()
    try:
        from services.report_service import ReportService
    except ImportError:
        return "Platform reports unavailable: backend not importable."

    ticker = ticker.strip().upper()
    svc = ReportService()
    dates = svc.list_report_dates(ticker)

    if not dates:
        return f"No historical reports found for {ticker} on FlowDeck."

    lines = [
        f"# Historical Report Dates for {ticker}",
        f"Found {len(dates)} analysis run(s) — newest first:",
        "",
    ]
    for i, run_id in enumerate(dates[:20], 1):
        lines.append(f"{i}. `{run_id}`")

    if len(dates) > 20:
        lines.append(f"... and {len(dates) - 20} more.")

    lines.append("")
    lines.append(
        "To fetch reports from a specific date, call get_platform_reports with "
        "the date parameter set to one of the run IDs above."
    )
    return "\n".join(lines)

# Made with Bob

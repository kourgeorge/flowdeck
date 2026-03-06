gi"""
CompareStocksSkill — side-by-side multi-ticker comparison workflow.

Two modes:
  1. Current snapshot (no period): quote + fundamentals + indicators per ticker
  2. Historical comparison (period given): fetch real price data via
     get_multi_historical_prices, compute % returns, emit a chart

Skill discovery and activation is handled via compare-stocks/SKILL.md
following the agentskills.io standard — the LLM reads the description
and selects this skill; no regex or keyword matching is used.
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Optional

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="compare_stocks",
    version="1.1",
    description=(
        "Compare two or more stocks, market indices, or country markets side-by-side. "
        "Use when the user asks to compare markets, countries, sectors, or specific tickers — "
        "including over a time period (e.g. 'last month', 'this year'). "
        "Handles natural-language market names such as 'usa market', 'israeli market', "
        "'s&p 500', 'nasdaq', 'ta-35'. Resolves names to ticker symbols automatically. "
        "When a period is specified, fetches real historical price data and computes % returns."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of resolved ticker symbols to compare, e.g. ['^GSPC', 'TA35.TA']",
                "minItems": 2,
                "maxItems": 6,
            },
            "period": {
                "type": "string",
                "description": (
                    "Optional time period for historical comparison. "
                    "Supported: 'week', 'month', 'this month', 'ytd', '1y', '3m', '6m', "
                    "or 'YYYY-MM-DD:YYYY-MM-DD'. If omitted, returns current snapshot."
                ),
            },
        },
        "required": ["tickers"],
    },
    tags=["comparison", "multi-stock", "analysis", "indices", "markets", "historical"],
    uses_tools=["get_ticker_quote", "get_fundamentals", "get_indicators", "get_multi_historical_prices"],
)


def _resolve_period(period: str) -> tuple[str, str, str]:
    """Resolve a period string to (start_date, end_date, label)."""
    today = datetime.date.today()
    p = period.lower().strip()

    if ":" in p:
        parts = p.split(":", 1)
        try:
            start = datetime.date.fromisoformat(parts[0].strip())
            end = datetime.date.fromisoformat(parts[1].strip())
            return start.isoformat(), end.isoformat(), f"{start} to {end}"
        except ValueError:
            pass

    if p in ("week", "last week", "1w"):
        days_since_monday = today.weekday()
        last_monday = today - datetime.timedelta(days=days_since_monday + 7)
        last_friday = last_monday + datetime.timedelta(days=4)
        return last_monday.isoformat(), last_friday.isoformat(), "Last Week"

    if p in ("this week", "current week"):
        days_since_monday = today.weekday()
        this_monday = today - datetime.timedelta(days=days_since_monday)
        return this_monday.isoformat(), today.isoformat(), "This Week"

    if p in ("month", "last month", "1m"):
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - datetime.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start.isoformat(), last_month_end.isoformat(), "Last Month"

    if p in ("this month", "current month"):
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), "This Month"

    if p in ("ytd", "year to date"):
        start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat(), "Year-to-Date"

    if p in ("1y", "1 year", "one year", "past year", "last year"):
        start = today - datetime.timedelta(days=365)
        return start.isoformat(), today.isoformat(), "Past 1 Year"

    if p in ("3m", "3 months", "three months"):
        start = today - datetime.timedelta(days=90)
        return start.isoformat(), today.isoformat(), "Past 3 Months"

    if p in ("6m", "6 months", "six months"):
        start = today - datetime.timedelta(days=180)
        return start.isoformat(), today.isoformat(), "Past 6 Months"

    # Default: last month
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - datetime.timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start.isoformat(), last_month_end.isoformat(), "Last Month"


def _compute_returns(prices_json: str, tickers: list[str]) -> list[dict]:
    """Parse multi-ticker price JSON and compute % returns."""
    import csv
    import io

    try:
        raw = json.loads(prices_json)
    except Exception:
        return []

    data = raw.get("data", {})
    results = []

    for ticker in tickers:
        csv_str = data.get(ticker) or data.get(ticker.upper())
        if not csv_str:
            continue
        try:
            reader = csv.DictReader(io.StringIO(csv_str))
            rows = [r for r in reader if r.get("Close")]
            if len(rows) < 2:
                continue
            first_close = float(rows[0]["Close"])
            last_close = float(rows[-1]["Close"])
            if first_close == 0:
                continue
            pct = (last_close - first_close) / first_close * 100
            results.append({
                "ticker": ticker,
                "start_price": round(first_close, 2),
                "end_price": round(last_close, 2),
                "return_pct": round(pct, 2),
                "start_date": rows[0].get("Date", ""),
                "end_date": rows[-1].get("Date", ""),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    return results


class CompareStocksSkill(BaseSkill):
    spec = _SPEC

    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,
        *,
        tickers: list[str],
        period: Optional[str] = None,
        **_,
    ) -> SkillResult:
        if not tickers or len(tickers) < 2:
            return SkillResult(
                ok=False,
                error={"code": "INVALID_INPUT", "message": "At least 2 tickers are required for comparison."},
            )

        # Preserve original case for index symbols (^GSPC, TA35.TA)
        tickers = [t.strip() for t in tickers[:6]]
        steps: list[SkillStep] = []
        n = [0]

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        tickers_str = " vs ".join(tickers)

        # ----------------------------------------------------------------
        # Mode 1: Historical comparison (period specified)
        # ----------------------------------------------------------------
        if period:
            start_date, end_date, period_label = _resolve_period(period)

            prices_result = call(
                "get_multi_historical_prices",
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
            )

            if not prices_result.ok:
                # Fall through to snapshot mode
                period = None
            else:
                returns = _compute_returns(prices_result.to_str(), tickers)

                if not returns:
                    return SkillResult(
                        ok=False,
                        error={"code": "NO_DATA", "message": f"No price data found for {tickers_str} in period {period_label}."},
                        steps=steps,
                    )

                # Build markdown table
                lines = [
                    f"# ⚖️ Market Comparison: {tickers_str}",
                    f"**Period:** {period_label} ({start_date} → {end_date})",
                    "",
                    f"| {'Ticker':<12} | {'Start Price':>12} | {'End Price':>10} | {'Return':>10} |",
                    f"|{'-'*14}|{'-'*14}|{'-'*12}|{'-'*12}|",
                ]
                for r in returns:
                    sign = "+" if r["return_pct"] >= 0 else ""
                    lines.append(
                        f"| {r['ticker']:<12} | {r['start_price']:>12.2f} | {r['end_price']:>10.2f} | {sign}{r['return_pct']:>8.2f}% |"
                    )

                if returns:
                    best = returns[0]
                    worst = returns[-1]
                    lines.append("")
                    lines.append(f"**🏆 Best performer:** {best['ticker']} ({'+' if best['return_pct'] >= 0 else ''}{best['return_pct']:.2f}%)")
                    lines.append(f"**📉 Worst performer:** {worst['ticker']} ({'+' if worst['return_pct'] >= 0 else ''}{worst['return_pct']:.2f}%)")

                # Build chart spec
                chart_data = [{"ticker": r["ticker"], "return_pct": r["return_pct"]} for r in returns]
                chart = {
                    "title": f"% Return: {tickers_str} — {period_label}",
                    "type": "bar",
                    "xKey": "ticker",
                    "yKeys": ["return_pct"],
                    "data": chart_data,
                    "colors": ["#60a5fa"],
                }
                lines.append("")
                lines.append(f"CHART_JSON:{json.dumps(chart)}")

                return SkillResult(
                    ok=True,
                    data="\n".join(lines),
                    steps=steps,
                    metrics={"tool_calls": len(steps), "tickers_compared": len(tickers), "period": period_label},
                )

        # ----------------------------------------------------------------
        # Mode 2: Current snapshot (no period or historical fetch failed)
        # ----------------------------------------------------------------
        ticker_data: list[dict] = []
        for ticker in tickers:
            q = call("get_ticker_quote", symbol=ticker)
            f = call("get_fundamentals", ticker=ticker)
            ticker_data.append({
                "ticker": ticker,
                "quote": q.to_str() if q.ok else "N/A",
                "fundamentals": f.to_str() if f.ok else "N/A",
            })

        sections = [f"# ⚖️ Market Comparison: {tickers_str}", ""]
        sections.append("## 💰 Current Quotes")
        for td in ticker_data:
            sections.append(f"### {td['ticker']}")
            sections.append(td["quote"][:400])
            sections.append("")

        sections.append("## 📊 Fundamentals")
        for td in ticker_data:
            sections.append(f"### {td['ticker']}")
            sections.append(td["fundamentals"][:600])
            sections.append("")

        return SkillResult(
            ok=True,
            data="\n".join(sections),
            steps=steps,
            metrics={"tool_calls": len(steps), "tickers_compared": len(tickers)},
        )

# Made with Bob

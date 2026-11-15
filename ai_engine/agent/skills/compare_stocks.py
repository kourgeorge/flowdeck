"""
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

import json
from typing import Any, Optional

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext
from ai_engine.agent.skills._periods import (
    compute_period_returns,
    compute_period_returns_with_reasons,
    fetch_start_date,
    format_skipped_line,
    resolve_period,
)


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


# Kept as module names because tests and older callers import them from here.
_resolve_period = resolve_period
_compute_returns = compute_period_returns


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
            start_date, end_date, period_label = resolve_period(period, default="month")

            prices_result = call(
                "get_multi_historical_prices",
                tickers=tickers,
                start_date=fetch_start_date(start_date),
                end_date=end_date,
            )

            if not prices_result.ok:
                # Fall through to snapshot mode
                period = None
            else:
                returns, skipped = compute_period_returns_with_reasons(
                    prices_result.to_str(), tickers, start_date, end_date
                )

                if not returns:
                    message = f"No price data found for {tickers_str} in period {period_label}."
                    if skipped:
                        message += " " + format_skipped_line(skipped)
                    return SkillResult(
                        ok=False,
                        error={"code": "NO_DATA", "message": message},
                        steps=steps,
                    )

                # Title and chart name only the measured tickers; an
                # unmeasured one is listed separately with its reason.
                measured_str = " vs ".join(r["ticker"] for r in returns)
                lines = [
                    f"# ⚖️ Market Comparison: {measured_str}",
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

                # One measured stock would be named both best and worst.
                if len(returns) >= 2:
                    best = returns[0]
                    worst = returns[-1]
                    lines.append("")
                    lines.append(f"**🏆 Best performer:** {best['ticker']} ({'+' if best['return_pct'] >= 0 else ''}{best['return_pct']:.2f}%)")
                    lines.append(f"**📉 Worst performer:** {worst['ticker']} ({'+' if worst['return_pct'] >= 0 else ''}{worst['return_pct']:.2f}%)")

                # Stocks without a close before the start get no return rather
                # than one measured from a later day; say so instead of hiding them.
                if skipped:
                    lines.append("")
                    lines.append(format_skipped_line(skipped))

                # Build chart spec
                chart_data = [{"ticker": r["ticker"], "return_pct": r["return_pct"]} for r in returns]
                chart = {
                    "title": f"% Return: {measured_str} — {period_label}",
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
                    metrics={"tool_calls": len(steps), "tickers_compared": len(returns), "period": period_label},
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



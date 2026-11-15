"""
PortfolioPerformanceSkill — real-data weekly/monthly/yearly performance ranking.

Steps:
  1. get_user_subscriptions  — fetch the user's subscribed tickers
  2. get_multi_historical_prices — fetch real closing prices for ALL tickers at once
  3. Compute % returns, rank gainers/losers, emit CHART_JSON

IMPORTANT: This skill NEVER simulates or estimates returns — it always fetches
real historical price data via get_multi_historical_prices.

Skill discovery and activation is handled via portfolio-performance/SKILL.md
following the agentskills.io standard — the LLM reads the description
and selects this skill; no regex or keyword matching is used.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext
from ai_engine.agent.skills._periods import (
    compute_period_returns_with_reasons,
    fetch_start_date,
    format_skipped_line,
    resolve_period,
)


_SPEC = SkillSpec(
    name="portfolio_performance",
    version="1.0",
    description=(
        "Compute real portfolio performance — top gainers, top losers, and % returns — "
        "over a specified time period using actual historical price data. "
        "Use when the user asks about portfolio performance, top gainers, top losers, "
        "best or worst performers, weekly/monthly/yearly returns, or wants to rank their stocks. "
        "Never simulates or estimates — always fetches real market data."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "description": "Period: 'week', 'this week', 'month', 'this month', 'ytd', '1y', '3m', '6m', or 'YYYY-MM-DD:YYYY-MM-DD'",
            }
        },
        "required": [],
    },
    tags=["portfolio", "performance", "gainers", "losers", "returns", "ranking"],
    uses_tools=["get_user_subscriptions", "get_multi_historical_prices"],
)


class PortfolioPerformanceSkill(BaseSkill):
    spec = _SPEC

    def run(
        self,
        ctx: ExecutionContext,
        tool_executor: Any,
        *,
        period: str = "week",
        **_,
    ) -> SkillResult:
        steps: list[SkillStep] = []
        n = [0]

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        # ----------------------------------------------------------------
        # Step 1: Get subscribed tickers
        # ----------------------------------------------------------------
        subs_result = call("get_user_subscriptions")
        if not subs_result.ok:
            return SkillResult(
                ok=False,
                error={"code": "SUBSCRIPTIONS_FAILED", "message": subs_result.to_str()},
                steps=steps,
            )

        tickers = _parse_tickers(subs_result.to_str())
        if not tickers:
            return SkillResult(
                ok=True,
                data="You have no subscribed stocks yet. Visit the platform to subscribe to tickers.",
                steps=steps,
            )

        # ----------------------------------------------------------------
        # Step 2: Resolve date range from period
        # ----------------------------------------------------------------
        start_date, end_date, period_label = resolve_period(period, default="week")

        # ----------------------------------------------------------------
        # Step 3: Fetch real historical prices for ALL tickers at once
        # ----------------------------------------------------------------
        # Fetch from before start_date so the return can be measured from the
        # previous session's close; otherwise the first day's move is lost.
        prices_result = call(
            "get_multi_historical_prices",
            tickers=tickers,
            start_date=fetch_start_date(start_date),
            end_date=end_date,
        )
        if not prices_result.ok:
            return SkillResult(
                ok=False,
                error={"code": "PRICES_FAILED", "message": prices_result.to_str()},
                steps=steps,
            )

        prices_json = prices_result.to_str()

        # ----------------------------------------------------------------
        # Step 4: Compute returns in-process (no subprocess needed)
        # ----------------------------------------------------------------
        returns_table, chart_spec, measured = _returns_report(
            prices_json, period_label, start_date, end_date, tickers
        )

        # Build summary
        sections = [
            f"# 📈 Portfolio Performance — {period_label}",
            "",
            f"**Period:** {start_date} → {end_date}",
            # Count only the stocks that actually got a return, so a skipped
            # recent IPO doesn't inflate the number next to a shorter table.
            f"**Tickers analysed:** {measured}",
            "",
            "## Real-Data Returns",
            returns_table,
        ]

        if chart_spec:
            sections.append("")
            sections.append(f"CHART_JSON:{chart_spec}")

        return SkillResult(
            ok=True,
            data="\n".join(sections),
            steps=steps,
            metrics={
                "tool_calls": len(steps),
                "tickers": measured,
                "period": period_label,
            },
        )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tickers(subs_text: str) -> list[str]:
    """Extract ticker symbols from get_user_subscriptions output."""
    matches = re.findall(r"\*\*([A-Z0-9\-\.^]+)\*\*", subs_text)
    seen: set[str] = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _build_returns_report(
    prices_json: str,
    period_label: str,
    start_date: str,
    end_date: str,
) -> tuple[str, str]:
    """Returns (table_text, chart_json_str); see _returns_report."""
    table_text, chart_json_str, _ = _returns_report(prices_json, period_label, start_date, end_date)
    return table_text, chart_json_str


def _returns_report(
    prices_json: str,
    period_label: str,
    start_date: str,
    end_date: str,
    tickers: list[str] | None = None,
) -> tuple[str, str, int]:
    """
    Parse multi-ticker price JSON, compute % returns, and build:
      - A markdown table string (plus a line naming any skipped tickers)
      - A CHART_JSON string (bar chart)

    Returns (table_text, chart_json_str, number_of_tickers_measured).
    """
    try:
        raw = json.loads(prices_json)
    except Exception:
        return "Error: could not parse price data.", "", 0

    data = raw.get("data", {})
    if not data:
        failed = raw.get("tickers_failed", {})
        return f"No price data returned. Failures: {failed}", "", 0

    results, skipped = compute_period_returns_with_reasons(prices_json, tickers, start_date, end_date)
    returns = [
        (r["ticker"], r["return_pct"], r["start_price"], r["end_price"])
        for r in results
    ]
    # A stock with no close before the start (e.g. a recent IPO) gets no
    # return at all; name it so it isn't silently missing from the table.
    skipped_line = format_skipped_line(skipped)

    if not returns:
        text = "No valid price data found for the requested period."
        if skipped_line:
            text += "\n\n" + skipped_line
        return text, "", 0

    # Build markdown table
    lines = [
        f"| {'Ticker':<12} | {'Start Price':>12} | {'End Price':>10} | {'Return':>10} |",
        f"|{'-'*14}|{'-'*14}|{'-'*12}|{'-'*12}|",
    ]
    for ticker, pct, start_p, end_p in returns:
        sign = "+" if pct >= 0 else ""
        lines.append(f"| {ticker:<12} | {start_p:>12.2f} | {end_p:>10.2f} | {sign}{pct:>8.2f}% |")

    # With one measured stock, "top gainer" and "top loser" would name the
    # same stock, which reads as a ranking that never happened.
    if len(returns) >= 2:
        top = returns[0]
        bottom = returns[-1]
        lines.append("")
        lines.append(f"**🏆 Top gainer:** {top[0]} ({'+' if top[1] >= 0 else ''}{top[1]:.2f}%)")
        lines.append(f"**📉 Top loser:** {bottom[0]} ({'+' if bottom[1] >= 0 else ''}{bottom[1]:.2f}%)")

    if skipped_line:
        lines.append("")
        lines.append(skipped_line)

    table_text = "\n".join(lines)

    # Build CHART_JSON
    chart_data = [{"ticker": t, "return_pct": r} for t, r, _, _ in returns]
    chart = {
        "title": f"Portfolio % Return — {period_label} ({start_date} → {end_date})",
        "type": "bar",
        "xKey": "ticker",
        "yKeys": ["return_pct"],
        "data": chart_data,
        "colors": ["#60a5fa"],
    }
    chart_json_str = json.dumps(chart)

    return table_text, chart_json_str, len(returns)


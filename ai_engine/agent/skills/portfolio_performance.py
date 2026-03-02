"""
PortfolioPerformanceSkill — real-data weekly/monthly/yearly performance ranking.

Steps:
  1. get_user_subscriptions  — fetch the user's subscribed tickers
  2. get_multi_historical_prices — fetch real closing prices for ALL tickers at once
  3. execute_python — compute % returns, rank gainers/losers, emit CHART_JSON

This skill is triggered when the user asks about top gainers, top losers,
best/worst performers, or weekly/monthly/yearly performance of their portfolio.

IMPORTANT: This skill NEVER simulates or estimates returns — it always fetches
real historical price data via get_multi_historical_prices.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="portfolio_performance",
    version="1.0",
    description=(
        "Compute real portfolio performance (top gainers/losers) over a given period "
        "by fetching actual historical prices for all subscribed tickers. "
        "Never simulates or estimates — always uses real market data."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "description": "Period: 'week', 'month', 'ytd', '1y', or a date range like '2026-02-23:2026-02-27'",
            }
        },
        "required": [],
    },
    tags=["portfolio", "performance", "gainers", "losers", "returns"],
    uses_tools=["get_user_subscriptions", "get_multi_historical_prices", "execute_python"],
)

_INTENT_PATTERNS = [
    "top gainer",
    "top loser",
    "best performer",
    "worst performer",
    "biggest gainer",
    "biggest loser",
    "best stock",
    "worst stock",
    "portfolio performance",
    "how did my stocks",
    "how did my portfolio",
    "portfolio last week",
    "portfolio this week",
    "portfolio last month",
    "portfolio this month",
    "weekly performance",
    "monthly performance",
    "yearly performance",
    "ytd performance",
    "year to date",
    "which stock gained",
    "which stock lost",
    "gainers in my",
    "losers in my",
    "performance last week",
    "performance this week",
    "performance last month",
    "show me the top",
    "rank my",
]


class PortfolioPerformanceSkill(BaseSkill):
    spec = _SPEC
    intent_patterns = _INTENT_PATTERNS

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
        start_date, end_date, period_label = _resolve_period(period)

        # ----------------------------------------------------------------
        # Step 3: Fetch real historical prices for ALL tickers at once
        # ----------------------------------------------------------------
        prices_result = call(
            "get_multi_historical_prices",
            tickers=tickers,
            start_date=start_date,
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
        returns_table, chart_spec = _compute_returns(prices_json, period_label, start_date, end_date)

        # Build summary
        sections = [
            f"# 📈 Portfolio Performance — {period_label}",
            "",
            f"**Period:** {start_date} → {end_date}",
            f"**Tickers analysed:** {len(tickers)}",
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
                "tickers": len(tickers),
                "period": period_label,
            },
        )

    def matches(self, message: str) -> bool:
        msg_lower = message.lower()
        return any(p in msg_lower for p in self.intent_patterns)


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


def _resolve_period(period: str) -> tuple[str, str, str]:
    """
    Resolve a period string to (start_date, end_date, label).

    Supports: 'week', 'month', 'ytd', '1y', '3m', '6m',
              or explicit 'YYYY-MM-DD:YYYY-MM-DD'.
    """
    today = datetime.date.today()
    end = today

    # Explicit range
    if ":" in period:
        parts = period.split(":", 1)
        try:
            start = datetime.date.fromisoformat(parts[0].strip())
            end = datetime.date.fromisoformat(parts[1].strip())
            return start.isoformat(), end.isoformat(), f"{start} to {end}"
        except ValueError:
            pass

    p = period.lower().strip()

    if p in ("week", "last week", "1w"):
        # Last full Mon–Fri week
        # Find last Monday
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

    # Default: last week
    days_since_monday = today.weekday()
    last_monday = today - datetime.timedelta(days=days_since_monday + 7)
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.isoformat(), last_friday.isoformat(), "Last Week"


def _compute_returns(
    prices_json: str,
    period_label: str,
    start_date: str,
    end_date: str,
) -> tuple[str, str]:
    """
    Parse multi-ticker price JSON, compute % returns, and build:
      - A markdown table string
      - A CHART_JSON string (bar chart)

    Returns (table_text, chart_json_str).
    """
    import json
    import csv
    import io

    try:
        raw = json.loads(prices_json)
    except Exception:
        return "Error: could not parse price data.", ""

    data = raw.get("data", {})
    if not data:
        failed = raw.get("tickers_failed", {})
        return f"No price data returned. Failures: {failed}", ""

    returns: list[tuple[str, float, float, float]] = []

    for ticker, csv_str in data.items():
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
            returns.append((ticker, round(pct, 2), round(first_close, 2), round(last_close, 2)))
        except Exception:
            continue

    if not returns:
        return "No valid price data found for the requested period.", ""

    returns.sort(key=lambda x: x[1], reverse=True)

    # Build markdown table
    lines = [
        f"| {'Ticker':<12} | {'Start Price':>12} | {'End Price':>10} | {'Return':>10} |",
        f"|{'-'*14}|{'-'*14}|{'-'*12}|{'-'*12}|",
    ]
    for ticker, pct, start_p, end_p in returns:
        sign = "+" if pct >= 0 else ""
        lines.append(f"| {ticker:<12} | {start_p:>12.2f} | {end_p:>10.2f} | {sign}{pct:>8.2f}% |")

    top = returns[0]
    bottom = returns[-1]
    lines.append("")
    lines.append(f"**🏆 Top gainer:** {top[0]} ({'+' if top[1] >= 0 else ''}{top[1]:.2f}%)")
    lines.append(f"**📉 Top loser:** {bottom[0]} ({'+' if bottom[1] >= 0 else ''}{bottom[1]:.2f}%)")

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

    return table_text, chart_json_str

# Made with Bob
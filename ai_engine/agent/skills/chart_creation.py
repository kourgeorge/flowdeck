"""
CreateChartSkill — fetch historical prices and produce a line chart (CHART_JSON).

Use when the user asks for a chart, graph, or plot of one or more tickers over time.
Fetches real data via get_multi_historical_prices and outputs a single CHART_JSON
line so the UI renders the chart.

Skill discovery and activation: chart-creation/SKILL.md (agentskills.io standard).
"""

from __future__ import annotations

import csv
import datetime
import io
import json
from typing import Any, Optional

from ai_engine.agent.skill import BaseSkill, SkillResult, SkillSpec, SkillStep
from ai_engine.agent.tool import ExecutionContext


_SPEC = SkillSpec(
    name="chart_creation",
    version="1.0",
    description=(
        "Create a chart or graph of stock/index prices over time. "
        "Use when the user asks for a chart, graph, plot, or visualization of one or more tickers "
        "(e.g. 'chart of AAPL', 'graph TSLA and NVDA over the last year', 'plot the S&P 500'). "
        "Fetches real historical price data and outputs a line chart. "
        "Supports indices (^GSPC, TA35.TA) and 1–6 tickers."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols to chart, e.g. ['AAPL', 'MSFT'] or ['^GSPC', 'TA35.TA']. Min 1, max 6.",
                "minItems": 1,
                "maxItems": 6,
            },
            "period": {
                "type": "string",
                "description": (
                    "Time period: '1y', '6m', '3m', 'month', 'this month', 'ytd', "
                    "or 'YYYY-MM-DD:YYYY-MM-DD'. Default '1y'."
                ),
            },
        },
        "required": ["tickers"],
    },
    tags=["chart", "graph", "plot", "visualization", "time-series"],
    uses_tools=["get_multi_historical_prices"],
)

# Default colors for up to 6 series (line chart)
_CHART_COLORS = ["#60a5fa", "#f97316", "#22c55e", "#e879f9", "#eab308", "#06b6d4"]


def _resolve_period(period: Optional[str]) -> tuple[str, str, str]:
    """Return (start_date, end_date, label). Default 1y."""
    today = datetime.date.today()
    p = (period or "1y").strip().lower()

    if ":" in p:
        parts = p.split(":", 1)
        try:
            start = datetime.date.fromisoformat(parts[0].strip())
            end = datetime.date.fromisoformat(parts[1].strip())
            return start.isoformat(), end.isoformat(), f"{start} to {end}"
        except ValueError:
            pass

    if p in ("month", "last month", "1m"):
        first = today.replace(day=1)
        last_end = first - datetime.timedelta(days=1)
        last_start = last_end.replace(day=1)
        return last_start.isoformat(), last_end.isoformat(), "Last Month"
    if p in ("this month", "current month"):
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), "This Month"
    if p in ("ytd", "year to date"):
        start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat(), "Year-to-Date"
    if p in ("1y", "1 year", "one year", "past year", "last year", ""):
        start = today - datetime.timedelta(days=365)
        return start.isoformat(), today.isoformat(), "Past 1 Year"
    if p in ("3m", "3 months"):
        start = today - datetime.timedelta(days=90)
        return start.isoformat(), today.isoformat(), "Past 3 Months"
    if p in ("6m", "6 months"):
        start = today - datetime.timedelta(days=180)
        return start.isoformat(), today.isoformat(), "Past 6 Months"

    start = today - datetime.timedelta(days=365)
    return start.isoformat(), today.isoformat(), "Past 1 Year"


def _prices_to_line_chart_data(prices_json: str, tickers: list[str]) -> list[dict]:
    """
    Parse get_multi_historical_prices JSON and build list of {date, ticker1: close, ticker2: close, ...}.
    All tickers are aligned by date (intersection of dates so every row has all tickers).
    """
    try:
        raw = json.loads(prices_json)
    except Exception:
        return []
    data = raw.get("data", {})
    if not data:
        return []

    # Parse each ticker's CSV into list of (date, close)
    series: dict[str, list[tuple[str, float]]] = {}
    for t in tickers:
        csv_str = data.get(t) or data.get(t.upper())
        if not csv_str:
            continue
        try:
            reader = csv.DictReader(io.StringIO(csv_str))
            rows = [(r.get("Date", ""), float(r["Close"])) for r in reader if r.get("Close") and r.get("Date")]
            if rows:
                series[t] = rows
        except Exception:
            continue

    if not series:
        return []

    # Build date -> {ticker: close} (union of dates; missing ticker on a date = omitted)
    date_to_closes: dict[str, dict[str, float]] = {}
    for t, rows in series.items():
        for date, close in rows:
            if date not in date_to_closes:
                date_to_closes[date] = {}
            date_to_closes[date][t] = round(close, 2)

    out = []
    for date in sorted(date_to_closes.keys()):
        closes = date_to_closes[date]
        row: dict[str, Any] = {"date": date}
        for t in tickers:
            if t in closes:
                row[t] = closes[t]
        out.append(row)

    return out


class CreateChartSkill(BaseSkill):
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
        if not tickers:
            return SkillResult(
                ok=False,
                error={"code": "INVALID_INPUT", "message": "At least one ticker is required for chart creation."},
                steps=[],
            )

        tickers = [t.strip() for t in tickers[:6]]
        steps: list[SkillStep] = []
        n = [0]

        def call(tool_name: str, **kwargs):
            return self.call_tool(tool_executor, ctx, steps, n, tool_name, **kwargs)

        start_date, end_date, period_label = _resolve_period(period)

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

        chart_data = _prices_to_line_chart_data(prices_result.to_str(), tickers)
        if not chart_data:
            return SkillResult(
                ok=False,
                error={
                    "code": "NO_DATA",
                    "message": f"No price data found for {', '.join(tickers)} in period {period_label}.",
                },
                steps=steps,
            )

        y_keys = [t for t in tickers if t in (chart_data[0] if chart_data else {})]
        if not y_keys:
            return SkillResult(
                ok=False,
                error={"code": "NO_DATA", "message": "Could not build chart series from price data."},
                steps=steps,
            )

        closes_flat = []
        for row in chart_data:
            for t in y_keys:
                if t in row and isinstance(row[t], (int, float)):
                    closes_flat.append(row[t])
        y_min = min(closes_flat) if closes_flat else 0
        y_max = max(closes_flat) if closes_flat else 100
        padding = (y_max - y_min) * 0.1 or 1
        y_axis = {"min": round(y_min - padding, 2), "max": round(y_max + padding, 2)}

        chart = {
            "title": f"{' vs '.join(y_keys)} — {period_label}",
            "type": "line",
            "xKey": "date",
            "yKeys": y_keys,
            "data": chart_data,
            "colors": _CHART_COLORS[: len(y_keys)],
            "yAxisConfig": y_axis,
        }
        chart_json_str = json.dumps(chart)

        tickers_str = ", ".join(tickers)
        summary = (
            f"Line chart of **{tickers_str}** over {period_label} ({start_date} → {end_date}). "
            f"Data points: {len(chart_data)}."
        )
        data_blob = summary + "\n\n" + f"CHART_JSON:{chart_json_str}"

        return SkillResult(
            ok=True,
            data=data_blob,
            steps=steps,
            metrics={"tool_calls": len(steps), "tickers": len(tickers), "period": period_label},
        )

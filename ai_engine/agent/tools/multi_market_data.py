"""
MultiHistoricalPricesTool — fetch historical prices for multiple tickers at once.

This is the preferred tool when the user asks about:
  - Comparing performance of multiple stocks over a period
  - Top gainers/losers in a portfolio over a week/month/year
  - Normalized performance charts (e.g. US vs Israeli market)
  - Any multi-ticker return calculation

Returns a JSON string with per-ticker CSV data.
"""

from __future__ import annotations

import datetime
import json

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# MultiHistoricalPricesTool
# ---------------------------------------------------------------------------

_MULTI_HISTORICAL_PRICES_SPEC = ToolSpec(
    name="get_multi_historical_prices",
    version="1.0",
    description=(
        "Fetch daily closing prices for MULTIPLE tickers over a custom date range in a single call. "
        "Returns a JSON object mapping each ticker to its CSV price data. "
        "Use this — instead of calling get_historical_prices repeatedly — whenever the user asks about: "
        "top gainers/losers in a portfolio over a week/month/year, "
        "comparing performance of multiple stocks, "
        "normalized performance charts (e.g. US vs Israeli market indices), "
        "or any multi-ticker return calculation. "
        "After fetching, pass the JSON to execute_python for calculations and chart generation. "
        "IMPORTANT: Always use this tool with REAL date ranges — never simulate or estimate returns."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of Yahoo Finance ticker symbols, e.g. ['SPY', 'TA35.TA', 'AAPL', 'TSLA']. "
                    "For Israeli market use TA35.TA (TA-35 index). "
                    "For US market use SPY (S&P 500 ETF) or ^GSPC (S&P 500 index). "
                    "Maximum 20 tickers per call."
                ),
                "minItems": 1,
                "maxItems": 20,
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format, e.g. 2025-01-01",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format. Use today's date for the most recent data.",
            },
        },
        "required": ["tickers", "start_date", "end_date"],
    },
    tags=["market", "price", "history", "multi", "portfolio", "comparison"],
)


class MultiHistoricalPricesTool(BaseTool):
    spec = _MULTI_HISTORICAL_PRICES_SPEC

    def execute(
        self,
        ctx: ExecutionContext,
        *,
        tickers: list[str],
        start_date: str,
        end_date: str,
        **_,
    ) -> ToolResult:
        try:
            data = _fetch_multi_historical_prices(tickers, start_date, end_date)
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _fetch_multi_historical_prices(
    tickers: list[str],
    start_date: str,
    end_date: str,
) -> str:
    import csv
    import io

    from ai_engine.tradingagents.datasources.info_service_client import (
        get_ticker_data,
        require_info_service,
    )

    require_info_service()

    # Validate and clamp dates
    try:
        start_dt = datetime.date.fromisoformat(start_date)
        end_dt = datetime.date.fromisoformat(end_date)
    except ValueError:
        return "Error: invalid date format. Use YYYY-MM-DD (e.g. 2025-01-01)."

    today = datetime.date.today()
    if end_dt > today:
        end_dt = today

    max_start = today - datetime.timedelta(days=5 * 365)
    if start_dt < max_start:
        start_dt = max_start

    if start_dt >= end_dt:
        return "Error: start_date must be before end_date."

    tickers_upper = [t.strip().upper() for t in tickers[:20]]
    results: dict[str, str] = {}
    errors: dict[str, str] = {}

    for ticker in tickers_upper:
        try:
            raw = get_ticker_data(ticker, start_dt.isoformat(), end_dt.isoformat())
            if not raw or not raw.strip():
                errors[ticker] = f"No data found between {start_dt} and {end_dt}"
                continue
            # Parse CSV, keep Date and Close, output CSV
            reader = csv.DictReader(io.StringIO(raw))
            rows = []
            for row in reader:
                date_val = row.get("Date", row.get("date", ""))
                close_val = row.get("Close", row.get("close", ""))
                if date_val and close_val:
                    try:
                        rows.append({"Date": str(date_val)[:10], "Close": round(float(close_val), 4)})
                    except (ValueError, TypeError):
                        pass
            if not rows:
                errors[ticker] = f"No valid rows between {start_dt} and {end_dt}"
                continue
            out = io.StringIO()
            w = csv.DictWriter(out, fieldnames=["Date", "Close"])
            w.writeheader()
            w.writerows(rows)
            results[ticker] = out.getvalue()
        except Exception as e:
            errors[ticker] = str(e)

    output = {
        "period": {"start": start_dt.isoformat(), "end": end_dt.isoformat()},
        "tickers_fetched": list(results.keys()),
        "tickers_failed": errors,
        "data": results,
        "note": (
            "Each ticker's data is a CSV with columns: Date, Close (adjusted). "
            "Use pandas to parse: pd.read_csv(io.StringIO(data['TICKER'])). "
            "To compute % return: (last_close - first_close) / first_close * 100. "
            "To normalize to 100: close / first_close * 100."
        ),
    }

    return json.dumps(output)


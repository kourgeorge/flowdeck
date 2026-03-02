"""
Market data tools:
  - StockDataTool       — 30-day OHLCV history
  - HistoricalPricesTool — custom date range OHLCV (up to 5 years)
  - IndicatorsTool      — technical indicators (RSI, MACD, Bollinger, etc.)
"""

from __future__ import annotations

import datetime

from ai_engine.agent.tool import BaseTool, ExecutionContext, ToolResult, ToolSpec

# ---------------------------------------------------------------------------
# StockDataTool
# ---------------------------------------------------------------------------

_STOCK_DATA_SPEC = ToolSpec(
    name="get_stock_data",
    version="1.0",
    description=(
        "Get historical OHLCV (Open, High, Low, Close, Volume) price data for a ticker over the last 30 days. "
        "Use when the user asks about price history, recent price movement, or wants to see a price trend."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            }
        },
        "required": ["ticker"],
    },
    tags=["market", "price", "history"],
)


class StockDataTool(BaseTool):
    spec = _STOCK_DATA_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.core_stock_tools import get_stock_data
            today = datetime.date.today()
            start = (today - datetime.timedelta(days=30)).isoformat()
            end = today.isoformat()
            data = get_stock_data.invoke({"symbol": ticker.upper(), "start_date": start, "end_date": end})
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


# ---------------------------------------------------------------------------
# HistoricalPricesTool
# ---------------------------------------------------------------------------

_HISTORICAL_PRICES_SPEC = ToolSpec(
    name="get_historical_prices",
    version="1.0",
    description=(
        "Fetch daily OHLCV (Open, High, Low, Close, Volume) price history for a ticker over a custom date range "
        "(up to 5 years back). Returns CSV data with adjusted close prices. "
        "Use this — instead of get_stock_data — whenever the user asks about price history beyond the last 30 days: "
        "e.g. year-to-date performance, 1-year or multi-year returns, correlation between two stocks over a year, "
        "historical volatility, drawdown analysis, or any calculation that requires more than 30 days of price data. "
        "After fetching, pass the CSV to execute_python for calculations."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            },
            "start_date": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format, e.g. 2024-01-01",
            },
            "end_date": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format, e.g. 2025-01-01. Use today's date for the most recent data.",
            },
        },
        "required": ["ticker", "start_date", "end_date"],
    },
    tags=["market", "price", "history", "csv"],
)


class HistoricalPricesTool(BaseTool):
    spec = _HISTORICAL_PRICES_SPEC

    def execute(
        self,
        ctx: ExecutionContext,
        *,
        ticker: str,
        start_date: str,
        end_date: str,
        **_,
    ) -> ToolResult:
        try:
            data = _fetch_historical_prices(ticker, start_date, end_date)
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})


def _fetch_historical_prices(ticker: str, start_date: str, end_date: str) -> str:
    import yfinance as yf
    import pandas as pd

    ticker_upper = ticker.strip().upper()

    try:
        start_dt = datetime.date.fromisoformat(start_date)
        end_dt = datetime.date.fromisoformat(end_date)
    except ValueError:
        return "Error: invalid date format. Use YYYY-MM-DD (e.g. 2024-01-01)."

    today = datetime.date.today()
    if end_dt > today:
        end_dt = today

    max_start = today - datetime.timedelta(days=5 * 365)
    if start_dt < max_start:
        start_dt = max_start

    if start_dt >= end_dt:
        return "Error: start_date must be before end_date."

    data = yf.download(
        ticker_upper,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        multi_level_index=False,
        progress=False,
        auto_adjust=True,
    )

    if data is None or data.empty:
        return f"No price data found for {ticker_upper} between {start_dt} and {end_dt}."

    data = data.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
    data["Date"] = [str(d)[:10] for d in pd.to_datetime(data["Date"])]
    data[["Open", "High", "Low", "Close"]] = data[["Open", "High", "Low", "Close"]].round(4)

    csv_out = data.to_csv(index=False)
    header = (
        f"# Historical daily prices for {ticker_upper}\n"
        f"# Period: {start_dt} to {end_dt} | Rows: {len(data)}\n"
        f"# Columns: Date, Open, High, Low, Close (adjusted), Volume\n\n"
    )
    return header + csv_out


# ---------------------------------------------------------------------------
# IndicatorsTool
# ---------------------------------------------------------------------------

_INDICATORS_SPEC = ToolSpec(
    name="get_indicators",
    version="1.0",
    description=(
        "Get technical analysis indicators for a ticker over the last 30 days: "
        "RSI (momentum/overbought-oversold), MACD (trend/momentum), SMA/EMA (moving averages), "
        "Bollinger Bands (volatility), ATR (average true range), VWMA (volume-weighted). "
        "Use when the user asks about technical analysis, chart patterns, momentum, or support/resistance."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            }
        },
        "required": ["ticker"],
    },
    tags=["technical", "indicators", "market"],
)


class IndicatorsTool(BaseTool):
    spec = _INDICATORS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.agents.utils.technical_indicators_tools import get_indicators
            today = datetime.date.today().isoformat()
            data = get_indicators.invoke({
                "symbol": ticker.upper(),
                "indicator": "all",
                "curr_date": today,
                "look_back_days": 30,
            })
            return ToolResult(ok=True, data=data)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})

# Made with Bob

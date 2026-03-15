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
    name="get_ticker_data",
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
            from ai_engine.tradingagents.agents.utils.core_stock_tools import get_ticker_data
            today = datetime.date.today()
            start = (today - datetime.timedelta(days=30)).isoformat()
            end = today.isoformat()
            data = get_ticker_data.invoke({"symbol": ticker.upper(), "start_date": start, "end_date": end})
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
        "Use this — instead of get_ticker_data — whenever the user asks about price history beyond the last 30 days: "
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
    from ai_engine.tradingagents.datasources.info_service_client import (
        get_ticker_data,
        require_info_service,
    )

    require_info_service()
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

    raw = get_ticker_data(ticker_upper, start_dt.isoformat(), end_dt.isoformat())
    if not raw or not raw.strip():
        return f"No price data found for {ticker_upper} between {start_dt} and {end_dt}."

    header = (
        f"# Historical daily prices for {ticker_upper}\n"
        f"# Period: {start_dt} to {end_dt}\n"
        f"# Columns: Date, Open, High, Low, Close (adjusted), Volume\n\n"
    )
    return header + raw.strip()


# ---------------------------------------------------------------------------
# IndicatorsTool
# ---------------------------------------------------------------------------

_INDICATORS_SPEC = ToolSpec(
    name="get_indicators",
    version="1.0",
    description=(
        "Get all key technical analysis indicators for a ticker (last 5 trading days): "
        "RSI, MACD, MACD Signal, MACD Histogram, Bollinger Bands (middle/upper/lower), "
        "50 SMA, 200 SMA, 10 EMA, ATR, VWMA, MFI. "
        "Pass only the ticker symbol — all indicators are returned together. "
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


# Indicators fetched when the agent calls get_indicators(ticker=...)
_DEFAULT_INDICATORS = [
    "rsi", "macd", "macds", "macdh",
    "boll", "boll_ub", "boll_lb",
    "close_50_sma", "close_200_sma", "close_10_ema",
    "atr", "vwma", "mfi",
]


class IndicatorsTool(BaseTool):
    spec = _INDICATORS_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.datasources.info_service_client import (
                get_indicators,
                require_info_service,
            )
            require_info_service()
            today = datetime.date.today().isoformat()
            parts: list[str] = []
            errors: list[str] = []
            for ind in _DEFAULT_INDICATORS:
                try:
                    result = get_indicators(
                        ticker=ticker.upper(),
                        indicator=ind,
                        curr_date=today,
                        look_back_days=5,  # last 5 trading days is enough for a snapshot
                    )
                    parts.append(result)
                except Exception as ind_exc:
                    errors.append(f"{ind}: {ind_exc}")
            if not parts:
                raise RuntimeError(
                    f"All indicators failed for {ticker}: " + "; ".join(errors)
                )
            combined = f"# Technical Indicators for {ticker.upper()} (as of {today})\n\n"
            combined += "\n\n---\n\n".join(parts)
            if errors:
                combined += f"\n\n_Note: the following indicators could not be fetched: {', '.join(errors)}_"
            return ToolResult(ok=True, data=combined)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})

# ---------------------------------------------------------------------------
# SpecificIndicatorTool
# ---------------------------------------------------------------------------

_SPECIFIC_INDICATOR_SPEC = ToolSpec(
    name="get_specific_indicator",
    version="1.0",
    description=(
        "Get a specific technical indicator for a stock. Use when you need only one indicator "
        "instead of all indicators. Available indicators: rsi, macd, macds, macdh, boll, boll_ub, "
        "boll_lb, close_50_sma, close_200_sma, close_10_ema, atr, vwma, mfi. "
        "More efficient than get_indicators when you only need one specific indicator."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol, e.g. AAPL, MSFT, TSLA",
            },
            "indicator": {
                "type": "string",
                "description": (
                    "Technical indicator name. Choose from: rsi, macd, macds, macdh, boll, boll_ub, "
                    "boll_lb, close_50_sma, close_200_sma, close_10_ema, atr, vwma, mfi"
                ),
            },
        },
        "required": ["ticker", "indicator"],
    },
    tags=["technical", "indicators", "market"],
)


class SpecificIndicatorTool(BaseTool):
    spec = _SPECIFIC_INDICATOR_SPEC

    def execute(self, ctx: ExecutionContext, *, ticker: str, indicator: str, **_) -> ToolResult:
        try:
            from ai_engine.tradingagents.datasources.info_service_client import (
                get_indicators,
                require_info_service,
            )
            
            # Validate indicator
            if indicator not in _DEFAULT_INDICATORS:
                return ToolResult(
                    ok=False,
                    error={
                        "code": "INVALID_INDICATOR",
                        "message": f"Invalid indicator '{indicator}'. Choose from: {', '.join(_DEFAULT_INDICATORS)}"
                    }
                )
            
            require_info_service()
            today = datetime.date.today().isoformat()
            result = get_indicators(
                ticker=ticker.upper(),
                indicator=indicator,
                curr_date=today,
                look_back_days=5,  # last 5 trading days is enough for a snapshot
            )
            return ToolResult(ok=True, data=result)
        except Exception as exc:
            return ToolResult(ok=False, error={"code": "TOOL_ERROR", "message": str(exc)})




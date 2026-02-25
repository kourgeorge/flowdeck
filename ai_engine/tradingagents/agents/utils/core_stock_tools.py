from langchain_core.tools import tool
from typing import Annotated
from datetime import datetime, timezone
import json

import yfinance as yf

from ...dataflows.interface import route_to_vendor

try:
    from ...dataflows.info_service_client import (
        get_stock_data as get_stock_data_via_service,
        get_quote as get_quote_via_service,
        is_configured as info_service_configured,
    )
except ImportError:
    get_stock_data_via_service = None
    get_quote_via_service = None
    info_service_configured = lambda: False


@tool
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve stock price data (OHLCV) for a given ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise the configured core_stock_apis vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
    """
    if get_stock_data_via_service is not None and info_service_configured():
        return get_stock_data_via_service(symbol, start_date, end_date)
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


@tool
def get_stock_quote(
    symbol: Annotated[str, "ticker symbol of the company"],
) -> str:
    """
    Retrieve current stock quote information for a ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise falls back to yfinance.
    Returns:
        str: JSON string with quote fields including current_price and last_update_time.
    """
    ticker = symbol.upper()

    if get_quote_via_service is not None and info_service_configured():
        quote = get_quote_via_service(ticker)
        if quote:
            return json.dumps(quote, default=str)
        return json.dumps({"ticker": ticker, "error": "No quote data available from info service"})

    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info or {}
        fast_info = ticker_obj.fast_info or {}

        current_price = (
            fast_info.get("lastPrice")
            or info.get("currentPrice")
            or info.get("regularMarketPrice")
        )
        previous_close = (
            fast_info.get("previousClose")
            or info.get("previousClose")
            or info.get("regularMarketPreviousClose")
        )
        day_high = fast_info.get("dayHigh") or info.get("dayHigh") or info.get("regularMarketDayHigh")
        day_low = fast_info.get("dayLow") or info.get("dayLow") or info.get("regularMarketDayLow")
        volume = fast_info.get("volume") or info.get("volume") or info.get("regularMarketVolume")

        quote_payload = {
            "ticker": ticker,
            "current_price": float(current_price) if current_price is not None else None,
            "previous_close": float(previous_close) if previous_close is not None else None,
            "daily_change": (
                float(current_price) - float(previous_close)
                if current_price is not None and previous_close is not None
                else None
            ),
            "daily_change_percent": (
                ((float(current_price) - float(previous_close)) / float(previous_close)) * 100.0
                if current_price is not None and previous_close not in (None, 0)
                else None
            ),
            "day_high": float(day_high) if day_high is not None else None,
            "day_low": float(day_low) if day_low is not None else None,
            "volume": int(volume) if volume is not None else None,
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "market_state": fast_info.get("marketState"),
            "last_update_time": datetime.now(timezone.utc).isoformat(),
            "source": "yfinance",
        }
        return json.dumps(quote_payload, default=str)
    except Exception as e:
        return json.dumps({"ticker": ticker, "error": f"Failed to retrieve quote: {e}"})

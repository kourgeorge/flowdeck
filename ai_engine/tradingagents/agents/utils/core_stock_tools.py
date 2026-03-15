from langchain_core.tools import tool
from typing import Annotated
import json

from ...datasources.info_service_client import (
    get_ticker_data as get_ticker_data_via_service,
    get_quote,
    require_info_service,
)


@tool
def get_ticker_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve ticker price data (OHLCV) for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the ticker price data for the specified ticker symbol in the specified date range.
    """
    require_info_service()
    return get_ticker_data_via_service(symbol, start_date, end_date)


@tool
def get_ticker_quote(
    symbol: Annotated[str, "ticker symbol of the company"],
) -> str:
    """
    Retrieve current ticker quote information for a ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Returns:
        str: JSON string with quote fields including current_price and last_update_time.
    """
    require_info_service()
    ticker = symbol.upper()
    quote = get_quote(ticker)
    if quote:
        return json.dumps(quote, default=str)
    return json.dumps({"ticker": ticker, "error": "No quote data available from info service"})

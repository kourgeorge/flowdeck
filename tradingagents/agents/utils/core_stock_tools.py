from langchain_core.tools import tool
from typing import Annotated

from tradingagents.dataflows.interface import route_to_vendor

try:
    from tradingagents.dataflows.info_service_client import get_stock_data as get_stock_data_via_service, is_configured as info_service_configured
except ImportError:
    get_stock_data_via_service = None
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

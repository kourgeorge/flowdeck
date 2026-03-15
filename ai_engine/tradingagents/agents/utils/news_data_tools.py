from langchain_core.tools import tool
from typing import Annotated, Optional

from ...datasources.info_service_client import (
    get_news as get_news_via_service,
    get_global_news as get_global_news_via_service,
    get_insider_sentiment as get_insider_sentiment_via_service,
    get_insider_transactions as get_insider_transactions_via_service,
    require_info_service,
)


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    require_info_service()
    return get_news_via_service(ticker, start_date, end_date)


@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
    query: Annotated[Optional[str], "Optional search focus (e.g. key risks, inflation)"] = None,
) -> str:
    """
    Retrieve global news data.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
        query (Optional[str]): Optional focus for the search; vendors may use it to narrow results
    Returns:
        str: A formatted string containing global news data
    """
    require_info_service()
    return get_global_news_via_service(curr_date, look_back_days, limit, query=query)


@tool
def get_insider_sentiment(
    ticker: Annotated[str, "ticker symbol for the company"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve insider sentiment information about a company.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A report of insider sentiment data
    """
    require_info_service()
    return get_insider_sentiment_via_service(ticker, curr_date)


@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A report of insider transaction data
    """
    require_info_service()
    return get_insider_transactions_via_service(ticker, limit=50)

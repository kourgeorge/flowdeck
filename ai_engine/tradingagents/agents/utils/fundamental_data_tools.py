from langchain_core.tools import tool
from typing import Annotated, Optional
import json

from ...datasources.info_service_client import (
    get_fundamentals as get_fundamentals_via_service,
    get_financial_statements,
    get_analyst_recommendations,
    require_info_service,
)


def _statement_to_str(statements: dict, key: str) -> str:
    """Extract one statement from info service response and return as string."""
    st = (statements or {}).get("statements", {}).get(key, {})
    if st.get("format") == "json":
        return json.dumps(st.get("data"))
    return str(st.get("data", ""))


@tool
def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve comprehensive fundamental data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional when using info service)
    Returns:
        str: A formatted report containing comprehensive fundamental data
    """
    require_info_service()
    return get_fundamentals_via_service(ticker)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing balance sheet data
    """
    require_info_service()
    data = get_financial_statements(ticker, statement_type="balance_sheet", freq=freq)
    if data is not None:
        return _statement_to_str(data, "balance_sheet")
    return "No balance sheet data available"


@tool
def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing cash flow statement data
    """
    require_info_service()
    data = get_financial_statements(ticker, statement_type="cashflow", freq=freq)
    if data is not None:
        return _statement_to_str(data, "cashflow")
    return "No cash flow data available"


@tool
def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve income statement data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing income statement data
    """
    require_info_service()
    data = get_financial_statements(ticker, statement_type="income_statement", freq=freq)
    if data is not None:
        return _statement_to_str(data, "income_statement")
    return "No income statement data available"


@tool
def get_analysts_recommendation(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve analyst recommendation data for a given ticker symbol.
    Requires INFO_SERVICE_URL (backend). Agents work only with the backend.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: JSON payload containing recommendation, trend breakdown, and related metadata.
    """
    require_info_service()
    ticker_upper = ticker.upper()
    data = get_analyst_recommendations(ticker_upper)
    if data is not None:
        return json.dumps(data, default=str)
    return json.dumps({"ticker": ticker_upper, "error": "No analyst recommendation data available"})

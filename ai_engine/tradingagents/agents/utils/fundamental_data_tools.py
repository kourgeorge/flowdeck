from langchain_core.tools import tool
from typing import Annotated, Optional
import json

from ...dataflows.interface import route_to_vendor

try:
    from ...dataflows.info_service_client import (
        get_fundamentals as get_fundamentals_via_service,
        get_financial_statements,
        get_analyst_recommendations as get_analysts_recommendation_via_service,
        is_configured as info_service_configured,
    )
except ImportError:
    get_fundamentals_via_service = None
    get_financial_statements = None
    get_analysts_recommendation_via_service = None
    info_service_configured = lambda: False


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
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date you are trading at, yyyy-mm-dd (optional when using info service)
    Returns:
        str: A formatted report containing comprehensive fundamental data
    """
    if get_fundamentals_via_service is not None and info_service_configured():
        return get_fundamentals_via_service(ticker)
    return route_to_vendor("get_fundamentals", ticker, curr_date)


@tool
def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve balance sheet data for a given ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing balance sheet data
    """
    if get_financial_statements is not None and info_service_configured():
        data = get_financial_statements(ticker, statement_type="balance_sheet", freq=freq)
        if data is not None:
            return _statement_to_str(data, "balance_sheet")
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


@tool
def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve cash flow statement data for a given ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing cash flow statement data
    """
    if get_financial_statements is not None and info_service_configured():
        data = get_financial_statements(ticker, statement_type="cashflow", freq=freq)
        if data is not None:
            return _statement_to_str(data, "cashflow")
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


@tool
def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[Optional[str], "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """
    Retrieve income statement data for a given ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise the configured fundamental_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
        freq (str): Reporting frequency: annual/quarterly (default quarterly)
        curr_date (str): Current date you are trading at, yyyy-mm-dd
    Returns:
        str: A formatted report containing income statement data
    """
    if get_financial_statements is not None and info_service_configured():
        data = get_financial_statements(ticker, statement_type="income_statement", freq=freq)
        if data is not None:
            return _statement_to_str(data, "income_statement")
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


@tool
def get_analysts_recommendation(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve analyst recommendation data for a given ticker symbol.
    Uses the Information Service API when INFO_SERVICE_URL is set, otherwise falls back to yfinance.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: JSON payload containing recommendation, trend breakdown, and related metadata.
    """
    ticker_upper = ticker.upper()

    if get_analysts_recommendation_via_service is not None and info_service_configured():
        data = get_analysts_recommendation_via_service(ticker_upper)
        if data is not None:
            return json.dumps(data, default=str)

    from ...dataflows.y_finance import get_analyst_recommendations as get_yfinance_analyst_recommendations

    data = get_yfinance_analyst_recommendations(ticker_upper)
    return json.dumps(data, default=str)

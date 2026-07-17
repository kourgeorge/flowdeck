from langchain_core.tools import tool
from typing import Annotated, Optional
import json

from ...datasources.info_service_client import (
    get_fundamentals as get_fundamentals_via_service,
    get_financial_statements,
    get_analyst_recommendations,
    require_info_service,
)

_INDEX_ETF_QUOTE_TYPES = frozenset({"ETF", "ETN", "INDEX", "MUTUALFUND", "FUND"})
_INDEX_ETF_NAME_KEYWORDS = (
    " ETF",
    " ETN",
    " INDEX",
    " INDEX FUND",
    " TRUST",
    " FUND",
    " SPDR",
    " ISHARES",
    " VANGUARD",
    " INVESCO",
    " PROSHARES",
    " DIREXION",
)


def is_etf_or_index(ticker: str) -> bool:
    """Return True if *ticker* is an ETF, index fund, or similar non-company instrument.

    Fetches fundamentals from the info service and inspects QuoteType / AssetType fields
    plus name keywords — the same heuristic used by the valuation tools.
    Falls back to False when the info service is unavailable or returns no data.
    """
    try:
        raw = get_fundamentals_via_service(ticker)
        if not raw:
            return False
        fundamentals: dict = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return False

    def _upper(v) -> str:
        return str(v).upper().strip() if v else ""

    profile: dict = {}
    for key in ("CompanyProfile", "profile", "companyProfile", "AssetProfile"):
        val = fundamentals.get(key)
        if isinstance(val, dict):
            profile = val
            break

    # Check quote-type / asset-type fields
    type_fields = [
        fundamentals.get("QuoteType"),
        fundamentals.get("AssetType"),
        fundamentals.get("SecurityType"),
        fundamentals.get("InstrumentType"),
        fundamentals.get("Category"),
        fundamentals.get("FundFamily"),
        profile.get("quoteType"),
        profile.get("assetType"),
        profile.get("securityType"),
        profile.get("instrumentType"),
        profile.get("category"),
    ]
    normalized_types = " ".join(_upper(v) for v in type_fields if v)
    for keyword in _INDEX_ETF_QUOTE_TYPES:
        if keyword in normalized_types.split() or keyword in normalized_types:
            return True

    # Fall back to name-based check
    name_fields = [
        fundamentals.get("Name"),
        fundamentals.get("name"),
        profile.get("name"),
        profile.get("longName"),
        profile.get("shortName"),
    ]
    normalized_name = " ".join(_upper(v) for v in name_fields if v)
    return any(kw in normalized_name for kw in _INDEX_ETF_NAME_KEYWORDS)



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

"""SEC EDGAR filing content tool for the SEC analyst. Uses info service when configured."""

from langchain_core.tools import tool
from typing import Annotated, Optional

try:
    from tradingagents.dataflows.info_service_client import (
        get_edgar_filing_content as get_edgar_filing_content_via_service,
        is_configured as info_service_configured,
    )
except ImportError:
    get_edgar_filing_content_via_service = None
    info_service_configured = lambda: False


@tool
def get_edgar_filing_content(
    ticker: Annotated[str, "ticker symbol (e.g. AAPL, MSFT)"],
    form: Annotated[Optional[str], "10-K or 10-Q; omit for both"] = None,
    max_filings: Annotated[int, "maximum number of filings to include (default 1)"] = 1,
) -> str:
    """
    Retrieve SEC EDGAR filing content for a US company: Risk Factors, Management's Discussion and Analysis (MD&A), and Competition sections from 10-K/10-Q reports.
    Requires INFO_SERVICE_URL to be set so the backend can fetch and extract sections.
    Args:
        ticker: Ticker symbol of the company (e.g. AAPL).
        form: Optional '10-K' or '10-Q' to restrict to one form type.
        max_filings: Maximum number of filings to return (default 1).
    Returns:
        Formatted string with extracted sections for the SEC analyst to analyze.
    """
    if get_edgar_filing_content_via_service is not None and info_service_configured():
        return get_edgar_filing_content_via_service(ticker, form=form, limit=max_filings)
    return (
        "EDGAR filing content requires INFO_SERVICE_URL to be set (point to the backend API). "
        f"Cannot retrieve SEC content for {ticker.upper()}."
    )

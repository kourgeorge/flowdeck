"""
EDGAR data source: wraps EDGAR service for SEC filings.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class EdgarDataSource:
    """EDGAR filings data source delegating to get_edgar_service()."""

    def __init__(self, edgar_service: Any):
        """Expects the EDGAR service instance (from services.edgar_service)."""
        self._service = edgar_service

    def get_filings(self, ticker: str) -> Dict[str, Any]:
        return self._service.get_filings(ticker)

    def get_filing_content(
        self,
        ticker: str,
        form: Optional[str] = None,
        limit: int = 1,
    ) -> Dict[str, Any]:
        return self._service.get_filing_content(ticker, form, limit)

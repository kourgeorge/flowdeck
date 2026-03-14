"""
Report data source: wraps ReportService for platform AI analysis reports.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data_layer.sources.base import ReportDataSourceProtocol


class ReportDataSource:
    """Report data source delegating to ReportService."""

    def __init__(self, report_service: Any):
        """Expects a ReportService instance (from app_services or services.report_service)."""
        self._service = report_service

    def get_latest_execution_for_ticker(
        self, ticker: str
    ) -> Optional[tuple[int, str]]:
        return self._service.get_latest_execution_for_ticker(ticker)

    def get_analysis_run_for_date(
        self, ticker: str, date_str: str
    ) -> Optional[tuple[int, str]]:
        return self._service.get_analysis_run_for_date(ticker, date_str)

    def get_reports_with_scores(self, execution_id: int) -> Dict[str, Dict[str, Any]]:
        return self._service.get_reports_with_scores(execution_id)

    def get_reports_for_run(self, execution_id: int) -> Dict[str, Optional[str]]:
        return self._service.get_reports_for_run(execution_id)

    def get_historical_analyses(self, ticker: str) -> List[Dict[str, Any]]:
        return self._service.get_historical_analyses(ticker)

    def list_report_dates(self, ticker: str) -> List[str]:
        return self._service.list_report_dates(ticker)

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        return self._service.get_tickers_with_reports_for_date(date)

    def get_tickers_with_reports_for_date_paginated(
        self, date: str, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        return self._service.get_tickers_with_reports_for_date_paginated(
            date, limit, offset
        )

    def get_tickers_with_reports_for_recent_days(
        self, end_date: str, days: int
    ) -> List[str]:
        return self._service.get_tickers_with_reports_for_recent_days(end_date, days)

    def get_tickers_with_reports_for_recent_days_paginated(
        self, end_date: str, days: int, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        return self._service.get_tickers_with_reports_for_recent_days_paginated(
            end_date, days, limit, offset
        )

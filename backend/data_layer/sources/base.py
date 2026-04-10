"""
Data source protocols (abstract interfaces).

Each source is responsible for a domain: market, reports, user/portfolio, EDGAR.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class MarketDataSourceProtocol(Protocol):
    """Protocol for market data: quotes, company info, news, fundamentals, etc."""

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        ...

    def get_quotes_batch(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        ...

    def get_historical(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        ...

    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        ...

    def get_news_batch(
        self,
        tickers: List[str],
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        ...

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> Dict[str, Any]:
        ...

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        ...

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = "all",
        freq: str = "quarterly",
    ) -> Dict[str, Any]:
        ...

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        ...

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        ...

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_similar_tickers(
        self, ticker: str, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        ...

    def get_daily_market_movers(self, count: int = 8) -> Dict[str, Any]:
        ...

    def get_market_overview(
        self,
        limit_indices: int = 50,
        offset_indices: int = 0,
        limit_sectors: int = 50,
        offset_sectors: int = 0,
        limit_regions: int = 50,
        offset_regions: int = 0,
        limit_commodities: int = 50,
        offset_commodities: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        ...

    def get_market_overview_section(
        self,
        section: str,
        limit: int = 50,
        offset: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        ...

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        ...

    def refresh_market_overview_cache(self) -> None:
        ...

    def refresh_market_movers_cache(self) -> None:
        ...

    def get_indicators(
        self,
        ticker: str,
        indicator: str,
        curr_date: str,
        look_back_days: int = 30,
    ) -> str:
        ...

    def get_global_news(
        self,
        curr_date: str,
        lookback_days: int = 7,
        limit: int = 10,
        query: Optional[str] = None,
    ) -> str:
        ...

    def get_insider_sentiment(self, ticker: str, curr_date: str) -> str:
        ...

    def get_reddit_company_social(
        self, ticker: str, start_date: str, end_date: str, search_terms: list[str]
    ) -> str:
        ...


class ReportDataSourceProtocol(Protocol):
    """Protocol for platform reports (AI analysis reports)."""

    def get_latest_execution_for_ticker(
        self, ticker: str
    ) -> Optional[tuple[int, str]]:
        ...

    def get_latest_widget_data_for_tickers(
        self, tickers: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        ...

    def get_analysis_run_for_date(
        self, ticker: str, date_str: str
    ) -> Optional[tuple[int, str]]:
        ...

    def get_reports_with_scores(self, execution_id: int) -> Dict[str, Dict[str, Any]]:
        ...

    def get_reports_for_run(self, execution_id: int) -> Dict[str, Optional[str]]:
        ...

    def get_historical_analyses(self, ticker: str) -> List[Dict[str, Any]]:
        ...

    def list_report_dates(self, ticker: str) -> List[str]:
        ...

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        ...

    def get_tickers_with_reports_for_date_paginated(
        self, date: str, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        ...

    def get_tickers_with_reports_for_recent_days(
        self, end_date: str, days: int
    ) -> List[str]:
        ...

    def get_tickers_with_reports_for_recent_days_paginated(
        self, end_date: str, days: int, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        ...

    def get_latest_analyzed_tickers(self) -> List[str]:
        ...

    def get_latest_analyzed_tickers_paginated(
        self, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        ...


class UserPortfolioSourceProtocol(Protocol):
    """Protocol for user profile and portfolio data (read-only)."""

    def get_user_context(self, user_id: int, db: Any) -> str:
        ...


class EdgarSourceProtocol(Protocol):
    """Protocol for SEC EDGAR filings."""

    def get_filings(self, ticker: str) -> Dict[str, Any]:
        ...

    def get_filing_content(
        self,
        ticker: str,
        form: Optional[str] = None,
        limit: int = 1,
    ) -> Dict[str, Any]:
        ...

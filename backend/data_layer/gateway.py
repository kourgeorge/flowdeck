"""
DataGateway: single facade for all data access.

Delegates to pluggable sources (market, reports, user, EDGAR).
Used by REST API, AI agents, and other app components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data_layer.sources.base import (
    EdgarSourceProtocol,
    MarketDataSourceProtocol,
    ReportDataSourceProtocol,
    UserPortfolioSourceProtocol,
)


_data_gateway: Optional["DataGateway"] = None


class DataGateway:
    """
    Unified data access facade.
    Holds references to sources; all methods delegate to the appropriate source.
    """

    def __init__(
        self,
        market: MarketDataSourceProtocol,
        reports: ReportDataSourceProtocol,
        user: UserPortfolioSourceProtocol,
        edgar: EdgarSourceProtocol,
    ):
        self._market = market
        self._reports = reports
        self._user = user
        self._edgar = edgar

    # ---------- Market ----------
    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._market.get_quote(ticker)

    def get_quotes_batch(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        return self._market.get_quotes_batch(tickers)

    def get_historical(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        return self._market.get_historical(ticker, period=period, interval=interval)

    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        return self._market.get_news(
            ticker, vendor=vendor, lookback_days=lookback_days
        )

    def get_news_batch(
        self,
        tickers: List[str],
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        return self._market.get_news_batch(
            tickers, vendor=vendor, lookback_days=lookback_days
        )

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> Dict[str, Any]:
        return self._market.get_insider_transactions(ticker, limit=limit)

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_company_info(ticker)

    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        return self._market.get_company_info_batch(tickers)

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_extended_info(ticker)

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_fund_info(ticker)

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_fundamentals(ticker)

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = "all",
        freq: str = "quarterly",
    ) -> Dict[str, Any]:
        return self._market.get_financial_statements(
            ticker, statement_type=statement_type, freq=freq
        )

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        return self._market.get_financial_charts(ticker, freq=freq)

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        return self._market.get_ticker_data(ticker, start_date, end_date)

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_analyst_recommendations(ticker)

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_future_events(ticker)

    def get_similar_tickers(
        self, ticker: str, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        return self._market.get_similar_tickers(ticker, limit, offset)

    def get_daily_market_movers(self, count: int = 8) -> Dict[str, Any]:
        return self._market.get_daily_market_movers(count)

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
        return self._market.get_market_overview(
            limit_indices=limit_indices,
            offset_indices=offset_indices,
            limit_sectors=limit_sectors,
            offset_sectors=offset_sectors,
            limit_regions=limit_regions,
            offset_regions=offset_regions,
            limit_commodities=limit_commodities,
            offset_commodities=offset_commodities,
            range_=range_,
        )

    def get_market_overview_section(
        self,
        section: str,
        limit: int = 50,
        offset: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        return self._market.get_market_overview_section(
            section=section, limit=limit, offset=offset, range_=range_
        )

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        return self._market.get_company_officers(ticker)

    def refresh_market_overview_cache(self) -> None:
        self._market.refresh_market_overview_cache()

    def refresh_market_movers_cache(self) -> None:
        self._market.refresh_market_movers_cache()

    # ---------- Reports ----------
    def get_latest_execution_for_ticker(
        self, ticker: str
    ) -> Optional[tuple[int, str]]:
        return self._reports.get_latest_execution_for_ticker(ticker)

    def get_analysis_run_for_date(
        self, ticker: str, date_str: str
    ) -> Optional[tuple[int, str]]:
        return self._reports.get_analysis_run_for_date(ticker, date_str)

    def get_reports_with_scores(self, execution_id: int) -> Dict[str, Dict[str, Any]]:
        return self._reports.get_reports_with_scores(execution_id)

    def get_reports_for_run(self, execution_id: int) -> Dict[str, Optional[str]]:
        return self._reports.get_reports_for_run(execution_id)

    def get_historical_analyses(self, ticker: str) -> List[Dict[str, Any]]:
        return self._reports.get_historical_analyses(ticker)

    def list_report_dates(self, ticker: str) -> List[str]:
        return self._reports.list_report_dates(ticker)

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        return self._reports.get_tickers_with_reports_for_date(date)

    def get_tickers_with_reports_for_date_paginated(
        self, date: str, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        return self._reports.get_tickers_with_reports_for_date_paginated(
            date, limit, offset
        )

    def get_tickers_with_reports_for_recent_days(
        self, end_date: str, days: int
    ) -> List[str]:
        return self._reports.get_tickers_with_reports_for_recent_days(end_date, days)

    def get_tickers_with_reports_for_recent_days_paginated(
        self, end_date: str, days: int, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        return self._reports.get_tickers_with_reports_for_recent_days_paginated(
            end_date, days, limit, offset
        )

    # ---------- User ----------
    def get_user_context(self, user_id: int, db: Any) -> str:
        return self._user.get_user_context(user_id, db)

    # ---------- EDGAR ----------
    def get_edgar_filings(self, ticker: str) -> Dict[str, Any]:
        return self._edgar.get_filings(ticker)

    def get_edgar_filing_content(
        self,
        ticker: str,
        form: Optional[str] = None,
        limit: int = 1,
    ) -> Dict[str, Any]:
        return self._edgar.get_filing_content(ticker, form, limit)


def get_data_gateway() -> DataGateway:
    """Get the shared DataGateway instance. Must be initialized at startup."""
    if _data_gateway is None:
        raise RuntimeError(
            "Data gateway not initialized. Call init_data_gateway() at startup."
        )
    return _data_gateway


def init_data_gateway(
    market: MarketDataSourceProtocol,
    reports: ReportDataSourceProtocol,
    user: UserPortfolioSourceProtocol,
    edgar: EdgarSourceProtocol,
) -> DataGateway:
    """Initialize the shared DataGateway. Called from main.py at startup."""
    global _data_gateway
    _data_gateway = DataGateway(market=market, reports=reports, user=user, edgar=edgar)
    return _data_gateway

"""
Market data source: wraps CachedInfoFetcher (which wraps InfoFetcher).

Uses existing Yahoo-based implementation with SQLite TTL cache.
Option A (route_to_vendor) can be added later for multi-vendor support.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from data_layer.sources.base import MarketDataSourceProtocol


class CachedMarketSource:
    """
    Market data source delegating to CachedInfoFetcher.
    Implements MarketDataSourceProtocol.
    """

    def __init__(self, cached_fetcher: Any):
        """Expects a CachedInfoFetcher instance (from services.cached_info_fetcher)."""
        self._fetcher = cached_fetcher

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        return self._fetcher.get_quote(ticker)

    def get_quotes_batch(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        return self._fetcher.get_quotes_batch(tickers)

    def get_historical(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        return self._fetcher.get_historical(ticker, period=period, interval=interval)

    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        return self._fetcher.get_news(
            ticker, vendor=vendor, lookback_days=lookback_days
        )

    def get_news_batch(
        self,
        tickers: List[str],
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        return self._fetcher.get_news_batch(
            tickers, vendor=vendor, lookback_days=lookback_days
        )

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> Dict[str, Any]:
        return self._fetcher.get_insider_transactions(ticker, limit=limit)

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_company_info(ticker)

    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        return self._fetcher.get_company_info_batch(tickers)

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_extended_info(ticker)

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_fund_info(ticker)

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_fundamentals(ticker)

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = "all",
        freq: str = "quarterly",
    ) -> Dict[str, Any]:
        return self._fetcher.get_financial_statements(
            ticker, statement_type=statement_type, freq=freq
        )

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        return self._fetcher.get_financial_charts(ticker, freq=freq)

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        return self._fetcher.get_ticker_data(ticker, start_date, end_date)

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_analyst_recommendations(ticker)

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_future_events(ticker)

    def get_similar_tickers(
        self, ticker: str, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        return self._fetcher.get_similar_tickers(ticker, limit, offset)

    def get_daily_market_movers(self, count: int = 8) -> Dict[str, Any]:
        return self._fetcher.get_daily_market_movers(count)

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
        return self._fetcher.get_market_overview(
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
        return self._fetcher.get_market_overview_section(
            section=section, limit=limit, offset=offset, range_=range_
        )

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        return self._fetcher.get_company_officers(ticker)

    def refresh_market_overview_cache(self) -> None:
        self._fetcher.refresh_market_overview_cache()

    def refresh_market_movers_cache(self) -> None:
        self._fetcher.refresh_market_movers_cache()

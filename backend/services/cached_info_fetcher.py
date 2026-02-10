"""
CachedInfoFetcher: cache layer wrapping InfoFetcher to reduce third-party fetch delays.

Delegates to InfoFetcher on cache miss; returns cached value on hit.
Uses per-type TTLs from config.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from config import (
    DATA_CACHE_TTL_ANALYST,
    DATA_CACHE_TTL_COMPANY,
    DATA_CACHE_TTL_EXTENDED,
    DATA_CACHE_TTL_FINANCIAL_CHARTS,
    DATA_CACHE_TTL_FINANCIAL_STATEMENTS,
    DATA_CACHE_TTL_FUNDAMENTALS,
    DATA_CACHE_TTL_FUND_INFO,
    DATA_CACHE_TTL_HISTORICAL,
    DATA_CACHE_TTL_NEWS,
    DATA_CACHE_TTL_QUOTE,
    DATA_CACHE_TTL_STOCK_DATA,
)
from services.data_cache import get_cached, get_cached_batch
from services.info_fetcher import InfoFetcher


class CachedInfoFetcher:
    """
    Wrapper around InfoFetcher that caches results to avoid repeated third-party fetches.
    """

    def __init__(self, fetcher: InfoFetcher):
        self._fetcher = fetcher

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        key = f"quote:{ticker.upper()}"
        return get_cached(key, DATA_CACHE_TTL_QUOTE, lambda: self._fetcher.get_quote(ticker))

    def _is_valid_quote_price(self, val: Any) -> bool:
        """Return True if current_price is valid (positive, not NaN). Don't cache invalid quotes."""
        if val is None:
            return False
        try:
            p = float(val)
            return p > 0 and not math.isnan(p)
        except (TypeError, ValueError):
            return False

    def get_quotes_batch(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get quotes for multiple tickers using cache; on miss, fetches all missing in one batch."""
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        key_ttl_pairs = [(f"quote:{t}", DATA_CACHE_TTL_QUOTE) for t in tickers]

        def batch_fetch(missing_keys: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
            tickers_to_fetch = [k.replace("quote:", "") for k in missing_keys]
            svc = self._fetcher._get_market_data_service()
            batch = svc.get_multiple_quotes_batch(tickers_to_fetch)
            result: Dict[str, Optional[Dict[str, Any]]] = {}
            for k in missing_keys:
                t = k.replace("quote:", "")
                quote = batch.get(t)
                if quote is not None:
                    d = quote.model_dump()
                    if self._is_valid_quote_price(d.get("current_price")):
                        result[k] = d
                    else:
                        result[k] = None  # Don't cache invalid quotes
                else:
                    result[k] = None
            return result

        raw = get_cached_batch(key_ttl_pairs, batch_fetch)
        return {k.replace("quote:", ""): raw[k] for k in raw}

    def get_historical(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        key = f"historical:{ticker.upper()}:{period}:{interval}"
        return get_cached(
            key,
            DATA_CACHE_TTL_HISTORICAL,
            lambda: self._fetcher.get_historical(ticker, period=period, interval=interval),
        )

    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        v = vendor or "yfinance"
        key = f"news:{ticker.upper()}:{v}:{lookback_days}"
        return get_cached(
            key,
            DATA_CACHE_TTL_NEWS,
            lambda: self._fetcher.get_news(ticker, vendor=vendor, lookback_days=lookback_days),
        )

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        key = f"company:{ticker.upper()}"
        return get_cached(key, DATA_CACHE_TTL_COMPANY, lambda: self._fetcher.get_company_info(ticker))

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        key = f"extended:{ticker.upper()}"
        return get_cached(key, DATA_CACHE_TTL_EXTENDED, lambda: self._fetcher.get_extended_info(ticker))

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        key = f"fundamentals:{ticker.upper()}"
        return get_cached(key, DATA_CACHE_TTL_FUNDAMENTALS, lambda: self._fetcher.get_fundamentals(ticker))

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = "all",
        freq: str = "quarterly",
    ) -> Dict[str, Any]:
        key = f"fs:{ticker.upper()}:{statement_type}:{freq}"
        return get_cached(
            key,
            DATA_CACHE_TTL_FINANCIAL_STATEMENTS,
            lambda: self._fetcher.get_financial_statements(
                ticker, statement_type=statement_type, freq=freq
            ),
        )

    def get_stock_data(self, ticker: str, start_date: str, end_date: str) -> str:
        key = f"stock_data:{ticker.upper()}:{start_date}:{end_date}"
        return get_cached(
            key,
            DATA_CACHE_TTL_STOCK_DATA,
            lambda: self._fetcher.get_stock_data(ticker, start_date, end_date),
        )

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        key = f"charts:{ticker.upper()}:{freq}"
        return get_cached(
            key,
            DATA_CACHE_TTL_FINANCIAL_CHARTS,
            lambda: self._fetcher.get_financial_charts(ticker, freq=freq),
        )

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        key = f"analyst:{ticker.upper()}"
        return get_cached(
            key,
            DATA_CACHE_TTL_ANALYST,
            lambda: self._fetcher.get_analyst_recommendations(ticker),
        )

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        key = f"fund_info:{ticker.upper()}"
        return get_cached(
            key,
            DATA_CACHE_TTL_FUND_INFO,
            lambda: self._fetcher.get_fund_info(ticker),
        )

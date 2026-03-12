"""
CachedInfoFetcher: cache layer wrapping InfoFetcher to reduce third-party fetch delays.

Delegates to InfoFetcher on cache miss; returns cached value on hit.
Uses per-type TTLs from config.
"""

from __future__ import annotations

import logging
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
    DATA_CACHE_TTL_INSIDER_TRANSACTIONS,
    DATA_CACHE_TTL_MARKET_MOVERS,
    DATA_CACHE_TTL_MARKET_OVERVIEW,
    DATA_CACHE_TTL_NEWS,
    DATA_CACHE_TTL_QUOTE,
    DATA_CACHE_TTL_SIMILAR_TICKERS,
    DATA_CACHE_TTL_STOCK_DATA,
)
from services.data_cache import get_cached, get_cached_batch, get_cached_with_origin, refresh_cached
from services.info_fetcher import InfoFetcher

logger = logging.getLogger(__name__)


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

    def get_news_batch(
        self,
        tickers: List[str],
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """Fetch news for multiple tickers, merge and dedupe by article id/link, sort by date. Uses cache per ticker."""
        if not tickers:
            return {"articles": [], "count": 0}
        by_key: Dict[str, Dict[str, Any]] = {}
        for t in tickers:
            raw = self.get_news(t, vendor=vendor, lookback_days=lookback_days)
            ticker_upper = t.upper()
            for a in (raw.get("articles") or []):
                key = a.get("uuid") or a.get("link") or ""
                if not key:
                    continue
                existing = by_key.get(key)
                if existing:
                    if ticker_upper not in (existing.get("tickers") or []):
                        existing.setdefault("tickers", []).append(ticker_upper)
                else:
                    by_key[key] = {**a, "tickers": [ticker_upper]}
        articles = sorted(
            by_key.values(),
            key=(lambda x: (x.get("published_timestamp") or 0)),
            reverse=True,
        )
        return {"articles": articles, "count": len(articles)}

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> Dict[str, Any]:
        key = f"insider_transactions:{ticker.upper()}:{limit}"
        return get_cached(
            key,
            DATA_CACHE_TTL_INSIDER_TRANSACTIONS,
            lambda: self._fetcher.get_insider_transactions(ticker, limit=limit),
        )

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        key = f"company:{ticker.upper()}"
        return get_cached(key, DATA_CACHE_TTL_COMPANY, lambda: self._fetcher.get_company_info(ticker))

    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get company info for multiple tickers; on cache miss fetches all missing in one batch."""
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        key_ttl_pairs = [(f"company:{t}", DATA_CACHE_TTL_COMPANY) for t in tickers]

        def batch_fetch(missing_keys: List[str]) -> Dict[str, Dict[str, Any]]:
            to_fetch = [k.replace("company:", "") for k in missing_keys]
            batch = self._fetcher.get_company_info_batch(to_fetch)
            return {k: batch.get(k.replace("company:", ""), {}) for k in missing_keys}

        raw = get_cached_batch(key_ttl_pairs, batch_fetch)
        return {k.replace("company:", ""): raw[k] for k in raw if raw.get(k)}

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

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        key = f"ticker_data:{ticker.upper()}:{start_date}:{end_date}"
        return get_cached(
            key,
            DATA_CACHE_TTL_STOCK_DATA,
            lambda: self._fetcher.get_ticker_data(ticker, start_date, end_date),
        )

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        key = f"charts:{ticker.upper()}:{freq}"
        return get_cached(
            key,
            DATA_CACHE_TTL_FINANCIAL_CHARTS,
            lambda: self._fetcher.get_financial_charts(ticker, freq=freq),
        )

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        key = f"analyst:v5:{ticker.upper()}"
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

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        """Get upcoming earnings and ex-dividend dates (cached)."""
        key = f"future_events:{ticker.upper()}"
        return get_cached(
            key,
            DATA_CACHE_TTL_ANALYST,
            lambda: self._fetcher.get_future_events(ticker),
        )

    def get_similar_tickers(self, ticker: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Get similar tickers based on sector/industry matching (cached)."""
        # Version key so matcher behavior changes do not serve stale cached payloads.
        key = f"similar_tickers:v2:{ticker.upper()}:{limit}:{offset}"
        return get_cached(
            key,
            DATA_CACHE_TTL_SIMILAR_TICKERS,
            lambda: self._fetcher.get_similar_tickers(ticker, limit, offset),
        )

    def get_daily_market_movers(self, count: int = 8) -> Dict[str, Any]:
        """Get daily top gainers and losers (cached)."""
        key = f"market_movers:{count}"
        return get_cached(
            key,
            DATA_CACHE_TTL_MARKET_MOVERS,
            lambda: self._fetcher.get_daily_market_movers(count),
        )

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
        """Get market overview: indices, sectors, international, commodities (cached). Pagination via limit/offset per group. range_: 1d, 1w, 1mo, 3mo, ytd."""
        key = f"market_overview:{range_}:{limit_indices}:{offset_indices}:{limit_sectors}:{offset_sectors}:{limit_regions}:{offset_regions}:{limit_commodities}:{offset_commodities}"
        return get_cached(
            key,
            DATA_CACHE_TTL_MARKET_OVERVIEW,
            lambda: self._fetcher.get_market_overview(
                limit_indices=limit_indices,
                offset_indices=offset_indices,
                limit_sectors=limit_sectors,
                offset_sectors=offset_sectors,
                limit_regions=limit_regions,
                offset_regions=offset_regions,
                limit_commodities=limit_commodities,
                offset_commodities=offset_commodities,
                range_=range_,
            ),
        )

    def get_market_overview_section(
        self,
        section: str,
        limit: int = 50,
        offset: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        """Get a single section of the market overview (cached)."""
        key = f"market_overview_section:{section}:{range_}:{limit}:{offset}"
        value, from_cache = get_cached_with_origin(
            key,
            DATA_CACHE_TTL_MARKET_OVERVIEW,
            lambda: self._fetcher.get_market_overview_section(
                section=section,
                limit=limit,
                offset=offset,
                range_=range_,
            ),
        )
        if from_cache:
            logger.info(
                "Serving market overview section from cache (section=%s, range=%s, limit=%s)",
                section, range_, limit,
            )
        else:
            logger.info(
                "Cache miss for market overview section (section=%s, range=%s), fetched from Yahoo",
                section, range_,
            )
        return value

    def refresh_market_overview_cache(self) -> None:
        """
        Force-fetch market overview data and write it to the cache (TTL 15min).
        Called by a periodic job so Overview and Regional Map are warm without waiting on first request.
        Warms only the first page of each section (fewer tickers, faster refresh).
        """
        limit = 6  # First page size (TILES_PER_PAGE in MarketView)
        # Only first page: offset 0 for all sections (indices, sectors, regions, commodities)
        for range_ in ("1d", "1w", "1mo", "6mo", "ytd"):
            key = f"market_overview:{range_}:{limit}:0:{limit}:0:{limit}:0:{limit}:0"
            refresh_cached(
                key,
                DATA_CACHE_TTL_MARKET_OVERVIEW,
                lambda r=range_: self._fetcher.get_market_overview(
                    limit_indices=limit,
                    offset_indices=0,
                    limit_sectors=limit,
                    offset_sectors=0,
                    limit_regions=limit,
                    offset_regions=0,
                    limit_commodities=limit,
                    offset_commodities=0,
                    range_=r,
                ),
            )
        # Regional Map: first page only (15 items) to avoid Yahoo rate limits.
        # Map requests limit=100 for regions; those will miss cache and fetch on demand.
        for section, section_limit in (("regions", 15), ("indices", 15)):
            for range_ in ("1d", "1w", "1mo", "6mo", "ytd"):
                key = f"market_overview_section:{section}:{range_}:{section_limit}:0"
                refresh_cached(
                    key,
                    DATA_CACHE_TTL_MARKET_OVERVIEW,
                    lambda s=section, lim=section_limit, r=range_: self._fetcher.get_market_overview_section(
                        section=s,
                        limit=lim,
                        offset=0,
                        range_=r,
                    ),
                )

    def refresh_market_movers_cache(self) -> None:
        """
        Force-fetch market movers and write to cache so first request is fast.
        Warms the default count (8) and Market view pagination (16, 24 for pages 2–3).
        """
        for count in (8, 16, 24):
            refresh_cached(
                f"market_movers:{count}",
                DATA_CACHE_TTL_MARKET_MOVERS,
                lambda c=count: self._fetcher.get_daily_market_movers(c),
            )

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        """Get company officers/management team (cached)."""
        key = f"company_officers:{ticker.upper()}"
        return get_cached(
            key,
            DATA_CACHE_TTL_COMPANY,  # Use same TTL as company info
            lambda: self._fetcher.get_company_officers(ticker),
        )

"""
MarketDataLayer: data layer market implementation with cache and vendor routing.

App/agents → DataGateway → CachedMarketSource → MarketDataLayer → (cache) → vendors
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

from config import (
    DATA_CACHE_TTL_ANALYST,
    DATA_CACHE_TTL_COMPANY,
    DATA_CACHE_TTL_EXTENDED,
    DATA_CACHE_TTL_FINANCIAL_CHARTS,
    DATA_CACHE_TTL_FINANCIAL_STATEMENTS,
    DATA_CACHE_TTL_FUNDAMENTALS,
    DATA_CACHE_TTL_FUND_INFO,
    DATA_CACHE_TTL_GLOBAL_NEWS,
    DATA_CACHE_TTL_HISTORICAL,
    DATA_CACHE_TTL_INDICATORS,
    DATA_CACHE_TTL_INSIDER_SENTIMENT,
    DATA_CACHE_TTL_INSIDER_TRANSACTIONS,
    DATA_CACHE_TTL_MARKET_MOVERS,
    DATA_CACHE_TTL_MARKET_OVERVIEW,
    DATA_CACHE_TTL_NEWS,
    DATA_CACHE_TTL_QUOTE,
    DATA_CACHE_TTL_SIMILAR_TICKERS,
    DATA_CACHE_TTL_STOCK_DATA,
)
from services.data_cache import get_cached, get_cached_batch, get_cached_with_origin, refresh_cached

from data_layer.constants import MARKET_OVERVIEW_TICKERS, OVERVIEW_INTERNATIONAL_TICKERS
from data_layer.vendors import quote as quote_vendor
from data_layer.vendors import yahoo_query
from data_layer.vendors.interface import (
    get_global_news as interface_get_global_news,
    get_indicators as interface_get_indicators,
    get_insider_sentiment as interface_get_insider_sentiment,
    get_ticker_data as interface_get_ticker_data,
)
from data_layer.vendors.reddit_utils import get_reddit_company_social_online
from data_layer.vendors.y_finance import (
    get_analyst_recommendations as yf_get_analyst_recommendations,
    get_company_info as yf_get_company_info,
    get_extended_info as yf_get_extended_info,
    get_financial_charts as yf_get_financial_charts,
    get_financial_statements as yf_get_financial_statements,
    get_fund_info as yf_get_fund_info,
    get_fundamentals_core as yf_get_fundamentals_core,
    get_future_events as yf_get_future_events,
    get_historical_app_format as yf_get_historical,
    get_insider_transactions_app_format as yf_get_insider_transactions,
    get_news_app_format as yf_get_news,
    get_company_officers as yf_get_company_officers,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")

_valid_ranges = ("1d", "1w", "1mo", "3mo", "6mo", "ytd")


def _valid_price(val: Any) -> bool:
    if val is None:
        return False
    try:
        p = float(val)
        return p > 0 and not math.isnan(p)
    except (TypeError, ValueError):
        return False


def _cached(key: str, ttl: float, fetch: Callable[[], T]) -> T:
    return get_cached(key, ttl, fetch)


def _news_cache_key(ticker: str, vendor: str, lookback_days: int) -> str:
    return f"news:{ticker.upper()}:{vendor}:{lookback_days}"


def _ticker_from_news_cache_key(cache_key: str) -> str:
    parts = cache_key.split(":", 3)
    return parts[1] if len(parts) > 1 else ""


def _quote_to_item(ticker: str, name: str, q: Optional[Dict]) -> Dict[str, Any]:
    if q is None:
        return {"ticker": ticker, "name": name, "price": None, "change": None, "changePercent": None}
    cp = q.get("current_price")
    dc = q.get("daily_change")
    dcp = q.get("daily_change_percent")
    return {
        "ticker": ticker,
        "name": name,
        "price": round(float(cp), 2) if cp is not None else None,
        "change": round(float(dc), 2) if dc is not None else None,
        "changePercent": round(float(dcp), 2) if dcp is not None else None,
    }


def _build_overview_items(
    by_group: Dict[str, List[tuple]],
    quotes: Dict[str, Dict],
    group_key: str,
) -> List[Dict[str, Any]]:
    items = [_quote_to_item(t, name, quotes.get(t)) for t, name in by_group[group_key]]
    items.sort(key=lambda x: abs(x.get("changePercent") or 0), reverse=True)
    return items


def _fetch_company_info(ticker: str) -> Dict[str, Any]:
    batch = yahoo_query.get_company_info_batch([ticker])
    info = batch.get(ticker)
    if info and (info.get("sector") or info.get("industry") or info.get("name") != ticker):
        return info
    return yf_get_company_info(ticker)


class MarketDataLayer:
    """Cache + vendor routing. Implements MarketDataSourceProtocol."""

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Single-ticker quote with full fields (bid/ask, day high/low, 52-week range).
        Uses quote_full: cache key so batch-quote cache (limited fields) does not override."""
        def fetch():
            q = quote_vendor.get_quote(ticker)
            return q if q and _valid_price(q.get("current_price")) else None
        return _cached(f"quote_full:{ticker.upper()}", DATA_CACHE_TTL_QUOTE, fetch)

    def get_quotes_batch(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        key_ttl = [(f"quote:{t}", DATA_CACHE_TTL_QUOTE) for t in tickers]

        def batch_fetch(missing: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
            to_fetch = [k.replace("quote:", "") for k in missing]
            batch = quote_vendor.get_quotes_batch(to_fetch)
            result: Dict[str, Optional[Dict[str, Any]]] = {}
            for k in missing:
                t = k.replace("quote:", "")
                q = batch.get(t)
                result[k] = q if q and _valid_price(q.get("current_price")) else None
            return result
        raw = get_cached_batch(key_ttl, batch_fetch)
        return {k.replace("quote:", ""): raw[k] for k in raw}

    def get_historical(self, ticker: str, period: str = "6mo", interval: str = "1d") -> Dict[str, Any]:
        return _cached(f"historical:{ticker.upper()}:{period}:{interval}", DATA_CACHE_TTL_HISTORICAL,
                      lambda: yf_get_historical(ticker, period=period, interval=interval))

    def get_news(self, ticker: str, vendor: Optional[str] = None, lookback_days: int = 7) -> Dict[str, Any]:
        v = vendor or "yfinance"
        return _cached(_news_cache_key(ticker, v, lookback_days), DATA_CACHE_TTL_NEWS,
                      lambda: yf_get_news(ticker, lookback_days=lookback_days))

    def get_news_batch(self, tickers: List[str], vendor: Optional[str] = None, lookback_days: int = 7) -> Dict[str, Any]:
        if not tickers:
            return {"articles": [], "count": 0}
        normalized_tickers: List[str] = []
        seen_tickers = set()
        for ticker in tickers:
            ticker_upper = ticker.upper()
            if ticker_upper and ticker_upper not in seen_tickers:
                normalized_tickers.append(ticker_upper)
                seen_tickers.add(ticker_upper)

        cache_vendor = vendor or "yfinance"
        key_ttl = [
            (_news_cache_key(ticker, cache_vendor, lookback_days), DATA_CACHE_TTL_NEWS)
            for ticker in normalized_tickers
        ]

        def batch_fetch(missing_keys: List[str]) -> Dict[str, Dict[str, Any]]:
            if not missing_keys:
                return {}

            results: Dict[str, Dict[str, Any]] = {}
            work_items = [(cache_key, _ticker_from_news_cache_key(cache_key)) for cache_key in missing_keys]
            max_workers = min(8, len(work_items))

            def _fetch_one(ticker: str) -> Dict[str, Any]:
                return yf_get_news(ticker, lookback_days=lookback_days)

            if max_workers <= 1:
                for cache_key, ticker in work_items:
                    try:
                        results[cache_key] = _fetch_one(ticker)
                    except Exception as exc:
                        logger.warning("News batch fetch failed for %s: %s", ticker, exc, exc_info=True)
                        results[cache_key] = {
                            "ticker": ticker,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "articles": [],
                            "count": 0,
                            "error": str(exc),
                        }
                return results

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_item = {
                    executor.submit(_fetch_one, ticker): (cache_key, ticker)
                    for cache_key, ticker in work_items
                }
                for future in as_completed(future_to_item):
                    cache_key, ticker = future_to_item[future]
                    try:
                        results[cache_key] = future.result()
                    except Exception as exc:
                        logger.warning("News batch fetch failed for %s: %s", ticker, exc, exc_info=True)
                        results[cache_key] = {
                            "ticker": ticker,
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "articles": [],
                            "count": 0,
                            "error": str(exc),
                        }
            return results

        news_by_cache_key = get_cached_batch(key_ttl, batch_fetch)
        by_key: Dict[str, Dict] = {}
        for ticker in normalized_tickers:
            cache_key = _news_cache_key(ticker, cache_vendor, lookback_days)
            payload = news_by_cache_key.get(cache_key) or {}
            for a in (payload.get("articles") or []):
                key = a.get("uuid") or a.get("link") or ""
                if not key:
                    continue
                if key in by_key:
                    if ticker not in (by_key[key].get("tickers") or []):
                        by_key[key].setdefault("tickers", []).append(ticker)
                else:
                    by_key[key] = {**a, "tickers": [ticker]}
        articles = sorted(by_key.values(), key=lambda x: x.get("published_timestamp") or 0, reverse=True)
        return {"articles": articles, "count": len(articles)}

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> Dict[str, Any]:
        return _cached(f"insider_transactions:{ticker.upper()}:{limit}", DATA_CACHE_TTL_INSIDER_TRANSACTIONS,
                      lambda: yf_get_insider_transactions(ticker, limit=limit))

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"company:{ticker.upper()}", DATA_CACHE_TTL_COMPANY, lambda: _fetch_company_info(ticker))

    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        key_ttl = [(f"company:{t}", DATA_CACHE_TTL_COMPANY) for t in tickers]

        def batch_fetch(missing: List[str]) -> Dict[str, Dict[str, Any]]:
            to_fetch = [k.replace("company:", "") for k in missing]
            batch = yahoo_query.get_company_info_batch(to_fetch)
            for t in to_fetch:
                if t not in batch or (batch[t].get("sector") == "N/A" and batch[t].get("name") == t):
                    batch[t] = yf_get_company_info(t)
            return {k: batch.get(k.replace("company:", ""), {}) for k in missing}
        raw = get_cached_batch(key_ttl, batch_fetch)
        return {k.replace("company:", ""): raw[k] for k in raw if raw.get(k)}

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"extended:{ticker.upper()}", DATA_CACHE_TTL_EXTENDED, lambda: yf_get_extended_info(ticker))

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"fund_info:{ticker.upper()}", DATA_CACHE_TTL_FUND_INFO, lambda: yf_get_fund_info(ticker))

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        def fetch():
            tu = ticker.upper()
            curr = datetime.now().strftime("%Y-%m-%d")
            try:
                data = yf_get_fundamentals_core(tu, curr)
                return {"ticker": tu, "date": curr, "fundamentals": data}
            except Exception as e:
                return {"ticker": tu, "date": curr, "fundamentals": {}, "error": str(e)}
        return _cached(f"fundamentals:{ticker.upper()}", DATA_CACHE_TTL_FUNDAMENTALS, fetch)

    def get_financial_statements(self, ticker: str, statement_type: str = "all", freq: str = "quarterly") -> Dict[str, Any]:
        return _cached(f"fs:{ticker.upper()}:{statement_type}:{freq}", DATA_CACHE_TTL_FINANCIAL_STATEMENTS,
                      lambda: yf_get_financial_statements(ticker, statement_type=statement_type, freq=freq))

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        return _cached(f"charts:{ticker.upper()}:{freq}", DATA_CACHE_TTL_FINANCIAL_CHARTS,
                      lambda: yf_get_financial_charts(ticker, freq=freq))

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        return _cached(f"ticker_data:{ticker.upper()}:{start_date}:{end_date}", DATA_CACHE_TTL_STOCK_DATA,
                      lambda: interface_get_ticker_data(ticker, start_date, end_date))

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"analyst:v5:{ticker.upper()}", DATA_CACHE_TTL_ANALYST, lambda: yf_get_analyst_recommendations(ticker))

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"future_events:{ticker.upper()}", DATA_CACHE_TTL_ANALYST, lambda: yf_get_future_events(ticker))

    def get_similar_tickers(self, ticker: str, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        return _cached(f"similar_tickers:v2:{ticker.upper()}:{limit}:{offset}", DATA_CACHE_TTL_SIMILAR_TICKERS,
                      lambda: yahoo_query.get_similar_tickers(ticker, limit=limit, offset=offset, get_quotes_batch=self.get_quotes_batch))

    def get_daily_market_movers(self, count: int = 8) -> Dict[str, Any]:
        return _cached(f"market_movers:{count}", DATA_CACHE_TTL_MARKET_MOVERS,
                      lambda: yahoo_query.get_daily_market_movers(count))

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        return _cached(f"company_officers:{ticker.upper()}", DATA_CACHE_TTL_COMPANY, lambda: yf_get_company_officers(ticker))

    def get_indicators(self, ticker: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
        return _cached(f"indicators:{ticker.upper()}:{indicator}:{curr_date}:{look_back_days}", DATA_CACHE_TTL_INDICATORS,
                      lambda: interface_get_indicators(ticker, indicator, curr_date, look_back_days))

    def get_global_news(self, curr_date: str, lookback_days: int = 7, limit: int = 10, query: Optional[str] = None) -> str:
        return _cached(f"global_news:{curr_date}:{lookback_days}:{limit}:{query or ''}", DATA_CACHE_TTL_GLOBAL_NEWS,
                      lambda: interface_get_global_news(curr_date, lookback_days, limit, query=query))

    def get_insider_sentiment(self, ticker: str, curr_date: str) -> str:
        return _cached(f"insider_sentiment:{ticker.upper()}:{curr_date}", DATA_CACHE_TTL_INSIDER_SENTIMENT,
                      lambda: interface_get_insider_sentiment(ticker, curr_date))

    def get_reddit_company_social(
        self, ticker: str, start_date: str, end_date: str, search_terms: list[str]
    ) -> str:
        """Reddit company social/discussion feed from finance subreddits. search_terms from agent (e.g. company name + ticker)."""
        terms_key = ",".join(sorted(t.strip() for t in search_terms if t and t.strip()))
        return _cached(
            f"reddit_company_social:{ticker.upper()}:{start_date}:{end_date}:{terms_key}",
            DATA_CACHE_TTL_NEWS,
            lambda: get_reddit_company_social_online(ticker.upper(), start_date, end_date, search_terms),
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
        key = f"market_overview:{range_}:{limit_indices}:{offset_indices}:{limit_sectors}:{offset_sectors}:{limit_regions}:{offset_regions}:{limit_commodities}:{offset_commodities}"
        return _cached(key, DATA_CACHE_TTL_MARKET_OVERVIEW,
                      lambda: self._do_market_overview(limit_indices, offset_indices, limit_sectors, offset_sectors,
                                                       limit_regions, offset_regions, limit_commodities, offset_commodities, range_))

    def _do_market_overview(
        self,
        limit_indices: int,
        offset_indices: int,
        limit_sectors: int,
        offset_sectors: int,
        limit_regions: int,
        offset_regions: int,
        limit_commodities: int,
        offset_commodities: int,
        range_: str,
    ) -> Dict[str, Any]:
        range_ = range_ if range_ in _valid_ranges else "1d"
        use_overview_regions = limit_regions <= 18
        by_group: Dict[str, List[tuple]] = {"indices": [], "sectors": [], "international": [], "commodities": []}
        for gk, t, n in MARKET_OVERVIEW_TICKERS:
            if gk == "international" and use_overview_regions:
                continue
            by_group[gk].append((t.upper(), n))
        if use_overview_regions:
            for _, t, n in OVERVIEW_INTERNATIONAL_TICKERS:
                by_group["international"].append((t.upper(), n))

        quotes: Dict[str, Dict] = {}
        for gk in ("indices", "sectors", "international", "commodities"):
            ticks = [t for t, _ in by_group[gk]]
            if ticks:
                for t, q in quote_vendor.get_quotes_batch_with_range(ticks, range_=range_).items():
                    if q:
                        quotes[t] = q
        if not quotes:
            src = OVERVIEW_INTERNATIONAL_TICKERS if use_overview_regions else MARKET_OVERVIEW_TICKERS
            all_ticks = list({t.upper() for _, t, _ in src})
            if all_ticks:
                for t, q in quote_vendor.get_quotes_batch_with_range(all_ticks, range_=range_).items():
                    if q:
                        quotes[t] = q

        idx = _build_overview_items(by_group, quotes, "indices")
        sec = _build_overview_items(by_group, quotes, "sectors")
        intl = _build_overview_items(by_group, quotes, "international")
        comm = _build_overview_items(by_group, quotes, "commodities")
        return {
            "indices": idx[offset_indices:offset_indices + limit_indices],
            "sectors": sec[offset_sectors:offset_sectors + limit_sectors],
            "international": intl[offset_regions:offset_regions + limit_regions],
            "commodities": comm[offset_commodities:offset_commodities + limit_commodities],
            "totalIndices": len(idx),
            "totalSectors": len(sec),
            "totalRegions": len(intl),
            "totalCommodities": len(comm),
        }

    def get_market_overview_section(self, section: str, limit: int = 50, offset: int = 0, range_: str = "1d") -> Dict[str, Any]:
        range_ = range_ if range_ in _valid_ranges else "1d"
        section_map = {"indices": "indices", "sectors": "sectors", "regions": "international", "international": "international", "commodities": "commodities"}
        normalized = section.lower()
        if normalized not in section_map:
            raise ValueError(f"Invalid section '{section}'. Expected: indices, sectors, regions, commodities.")
        group_key = section_map[normalized]
        key = f"market_overview_section:{section}:{range_}:{limit}:{offset}"
        value, from_cache = get_cached_with_origin(key, DATA_CACHE_TTL_MARKET_OVERVIEW,
                                                   lambda: self._do_market_overview_section(group_key, limit, offset, range_))
        logger.info("Market overview section %s (section=%s, range=%s)", "cache" if from_cache else "fetch", section, range_)
        return value

    def _do_market_overview_section(self, group_key: str, limit: int, offset: int, range_: str) -> Dict[str, Any]:
        group_tickers = [(t.upper(), n) for g, t, n in MARKET_OVERVIEW_TICKERS if g == group_key]
        if not group_tickers:
            sec = "regions" if group_key == "international" else group_key
            return {"section": sec, "items": [], "total": 0}
        ticks = list({t for t, _ in group_tickers})
        batch = quote_vendor.get_quotes_batch_with_range(ticks, range_=range_)
        quotes = {t: batch.get(t) for t in ticks}
        items = _build_overview_items({group_key: group_tickers}, quotes, group_key)
        sec = "regions" if group_key == "international" else group_key
        return {"section": sec, "items": items[offset:offset + limit], "total": len(items)}

    def refresh_market_overview_cache(self) -> None:
        limit = 6
        for r in ("1d", "1w", "1mo", "6mo", "ytd"):
            key = f"market_overview:{r}:{limit}:0:{limit}:0:{limit}:0:{limit}:0"
            refresh_cached(key, DATA_CACHE_TTL_MARKET_OVERVIEW,
                          lambda rng=r: self.get_market_overview(limit_indices=limit, offset_indices=0, limit_sectors=limit,
                              offset_sectors=0, limit_regions=limit, offset_regions=0, limit_commodities=limit, offset_commodities=0, range_=rng))
        for sec, sl in (("regions", 15), ("indices", 15)):
            for r in ("1d", "1w", "1mo", "6mo", "ytd"):
                key = f"market_overview_section:{sec}:{r}:{sl}:0"
                refresh_cached(key, DATA_CACHE_TTL_MARKET_OVERVIEW,
                              lambda s=sec, rng=r, lim=sl: self.get_market_overview_section(section=s, limit=lim, offset=0, range_=rng))

    def refresh_market_movers_cache(self) -> None:
        for count in (8, 16, 24):
            refresh_cached(f"market_movers:{count}", DATA_CACHE_TTL_MARKET_MOVERS,
                          (lambda c: lambda: yahoo_query.get_daily_market_movers(c))(count))

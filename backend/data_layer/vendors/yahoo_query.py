"""
YahooQuery vendor: company info, sector batch, daily movers, similar tickers.

All yahooquery access for market data lives in this module.
"""

from __future__ import annotations

import json
import logging
import math
import numbers
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        for key in ("raw", "value", "fmt", "longFmt"):
            if key in value:
                return _coerce_float(value.get(key))
        return None
    if isinstance(value, numbers.Real):
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except Exception:
        return None


def _default_company_info(symbol: str, quote_type: Any = None) -> Dict[str, Any]:
    if quote_type is None and symbol.startswith("^"):
        quote_type = "INDEX"
    return {
        "name": symbol,
        "sector": "N/A",
        "industry": "N/A",
        "exchange": "N/A",
        "country": "N/A",
        "website": "N/A",
        "quoteType": quote_type,
    }


def get_company_info_batch(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Get company profile for multiple tickers via yahooquery."""
    if not tickers:
        return {}
    symbols = [t.upper() for t in tickers]
    try:
        from yahooquery import Ticker as YahooQueryTicker
    except ImportError:
        return {t: _default_company_info(t) for t in symbols}
    try:
        ticker_obj = YahooQueryTicker(symbols)
        raw = ticker_obj.get_modules("price quoteType summaryProfile")
    except Exception:
        return {t: _default_company_info(t) for t in symbols}
    if not isinstance(raw, dict):
        return {t: _default_company_info(t) for t in symbols}
    result: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        per = raw.get(symbol) or raw.get(symbol.upper()) or raw.get(symbol.lower())
        if not isinstance(per, dict):
            result[symbol] = _default_company_info(symbol)
            continue
        price = per.get("price") if isinstance(per.get("price"), dict) else {}
        quote_type = per.get("quoteType") if isinstance(per.get("quoteType"), dict) else {}
        profile = per.get("summaryProfile") if isinstance(per.get("summaryProfile"), dict) else {}
        name = (price or {}).get("longName") or (price or {}).get("shortName") or (profile or {}).get("longName") or (profile or {}).get("shortName") or symbol
        qt = (quote_type or price or {}).get("quoteType")
        if qt is None and symbol.startswith("^"):
            qt = "INDEX"
        result[symbol] = {
            "name": name,
            "sector": (profile or {}).get("sector") or "N/A",
            "industry": (profile or {}).get("industry") or "N/A",
            "exchange": (quote_type or {}).get("exchange") or "N/A",
            "country": (profile or {}).get("country") or "N/A",
            "website": (profile or {}).get("website") or "N/A",
            "quoteType": qt,
        }
    return result


def get_sector_info_batch(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch sector/industry and related info for multiple tickers via yahooquery."""
    if not symbols:
        return {}
    symbols = [s.upper() for s in symbols]
    try:
        from yahooquery import Ticker as YahooQueryTicker
    except ImportError:
        return {}
    try:
        ticker_obj = YahooQueryTicker(symbols)
        raw = ticker_obj.get_modules("price summaryProfile summaryDetail financialData defaultKeyStatistics")
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    for symbol in symbols:
        per = raw.get(symbol) or raw.get(symbol.upper()) or raw.get(symbol.lower())
        if not isinstance(per, dict):
            continue
        price = per.get("price") if isinstance(per.get("price"), dict) else {}
        profile = per.get("summaryProfile") if isinstance(per.get("summaryProfile"), dict) else {}
        detail = per.get("summaryDetail") if isinstance(per.get("summaryDetail"), dict) else {}
        financial = per.get("financialData") if isinstance(per.get("financialData"), dict) else {}
        key_stats = per.get("defaultKeyStatistics") if isinstance(per.get("defaultKeyStatistics"), dict) else {}
        if not profile and not price:
            continue
        name = (price or {}).get("longName") or (price or {}).get("shortName") or (profile or {}).get("longName") or (profile or {}).get("shortName") or symbol
        result[symbol] = {
            "name": name,
            "sector": (profile or {}).get("sector"),
            "industry": (profile or {}).get("industry"),
            "market_cap": _coerce_float((detail or price or {}).get("marketCap") or (price or {}).get("marketCap")),
            "quote_type": (price or {}).get("quoteType"),
            "trailing_pe": _coerce_float((detail or {}).get("trailingPE")),
            "forward_pe": _coerce_float((detail or {}).get("forwardPE")),
            "trailing_eps": _coerce_float((key_stats or {}).get("trailingEps")),
            "forward_eps": _coerce_float((key_stats or {}).get("forwardEps")),
            "ebitda": _coerce_float((financial or {}).get("ebitda")),
            "revenue": _coerce_float((financial or {}).get("totalRevenue")),
            "profit_margin": _coerce_float((financial or {}).get("profitMargins")),
            "gross_margin": _coerce_float((financial or {}).get("grossMargins")),
            "operating_margin": _coerce_float((financial or {}).get("operatingMargins")),
            "ebitda_margin": _coerce_float((financial or {}).get("ebitdaMargins")),
            "beta": _coerce_float((detail or key_stats or {}).get("beta")),
            "dividend_yield": _coerce_float((detail or {}).get("dividendYield")),
            "fifty_two_week_high": _coerce_float((detail or price or {}).get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _coerce_float((detail or price or {}).get("fiftyTwoWeekLow")),
            "target_mean_price": _coerce_float((financial or {}).get("targetMeanPrice")),
            "recommendation_key": (financial or {}).get("recommendationKey"),
        }
    return result


def get_daily_market_movers(count: int = 8) -> Dict[str, Any]:
    """Get daily top gainers, losers, most active from yahooquery Screener."""
    try:
        from yahooquery import Screener
    except ImportError:
        return {"gainers": [], "losers": [], "most_active": []}
    count = max(1, min(100, count))
    screen_ids = ["day_gainers", "day_losers", "most_actives"]
    try:
        raw = Screener().get_screeners(screen_ids, count=count)
    except Exception:
        return {"gainers": [], "losers": [], "most_active": []}
    if not isinstance(raw, dict):
        return {"gainers": [], "losers": [], "most_active": []}
    gainers_data = raw.get("day_gainers")
    losers_data = raw.get("day_losers")
    most_actives_data = raw.get("most_actives")
    quotes_g = gainers_data.get("quotes", []) if isinstance(gainers_data, dict) else []
    quotes_l = losers_data.get("quotes", []) if isinstance(losers_data, dict) else []
    quotes_ma = most_actives_data.get("quotes", []) if isinstance(most_actives_data, dict) else []

    def _norm(q: Dict[str, Any]) -> Dict[str, Any]:
        price = _coerce_float(q.get("regularMarketPrice"))
        change = _coerce_float(q.get("regularMarketChange"))
        prev_close = _coerce_float(q.get("regularMarketPreviousClose"))
        if change is not None and prev_close is not None and prev_close != 0:
            change_pct = (change / prev_close) * 100.0
        else:
            change_pct = _coerce_float(q.get("regularMarketChangePercent"))
            if change_pct is not None and abs(change_pct) <= 1.5 and change_pct != 0:
                change_pct = change_pct * 100.0
        return {
            "symbol": (q.get("symbol") or "").strip() or None,
            "shortName": (q.get("shortName") or q.get("longName") or "").strip() or None,
            "regularMarketPrice": round(price, 2) if price is not None else None,
            "regularMarketChange": round(change, 2) if change is not None else None,
            "regularMarketChangePercent": round(change_pct, 2) if change_pct is not None else None,
            "regularMarketPreviousClose": prev_close,
            "regularMarketVolume": int(q["regularMarketVolume"]) if q.get("regularMarketVolume") is not None else None,
        }

    gainers = [_norm(q) for q in quotes_g if isinstance(q, dict) and q.get("symbol")]
    losers = [_norm(q) for q in quotes_l if isinstance(q, dict) and q.get("symbol")]
    most_active = [_norm(q) for q in quotes_ma if isinstance(q, dict) and q.get("symbol")]
    all_symbols = [r["symbol"] for r in gainers + losers + most_active if r.get("symbol")]
    sector_map = get_sector_info_batch(all_symbols) if all_symbols else {}
    for row in gainers + losers + most_active:
        sym = row.get("symbol")
        if sym and sym in sector_map:
            info = sector_map[sym]
            row["sector"] = info.get("sector")
            row["industry"] = info.get("industry")
    return {"gainers": gainers, "losers": losers, "most_active": most_active}


def _load_major_tickers_and_cache() -> tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Load major tickers and sector cache from JSON. Returns (ticker_list, sector_cache)."""
    data_dir = Path(__file__).resolve().parent.parent.parent
    data_file = data_dir / "data" / "major_stocks_sectors.json"
    sector_cache: Dict[str, Dict[str, Any]] = {}
    major_tickers: List[str] = []
    if not data_file.exists():
        return major_tickers, sector_cache
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for ticker, info in data.items():
            if isinstance(info, dict) and not info.get("error"):
                sector_cache[ticker] = info
        major_tickers = list(data.keys())
    except Exception as e:
        logger.warning("Could not load major_stocks_sectors.json: %s", e)
    return major_tickers, sector_cache


def get_similar_tickers(
    ticker: str,
    limit: int = 10,
    offset: int = 0,
    get_quotes_batch: Optional[Callable[[List[str]], Dict[str, Optional[Dict[str, Any]]]]] = None,
) -> Dict[str, Any]:
    """Get similar tickers based on sector/industry matching.
    Optionally enrich with current_price/change_percent via get_quotes_batch."""
    ticker = ticker.upper()
    major_tickers, sector_cache = _load_major_tickers_and_cache()

    target_info = sector_cache.get(ticker)
    if not target_info:
        batch = get_company_info_batch([ticker])
        target_info = batch.get(ticker, {})
    if not target_info:
        return {
            "ticker": ticker,
            "sector": None,
            "industry": None,
            "similar_tickers": [],
            "count": 0,
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "error": "Failed to fetch ticker information",
        }

    target_sector = target_info.get("sector")
    target_industry = target_info.get("industry")
    target_quote_type = target_info.get("quoteType") or target_info.get("quote_type")

    if target_quote_type in ("INDEX", "CURRENCY", "CRYPTOCURRENCY"):
        return {
            "ticker": ticker,
            "sector": target_sector,
            "industry": target_industry,
            "similar_tickers": [],
            "count": 0,
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "match_type": "not_applicable",
            "message": f"Similar tickers not available for {target_quote_type} type",
        }

    if not target_sector and not target_industry:
        return {
            "ticker": ticker,
            "sector": None,
            "industry": None,
            "similar_tickers": [],
            "count": 0,
            "total_count": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "match_type": "no_data",
            "message": "No sector/industry data available for this ticker",
        }

    candidates = [t for t in major_tickers if t != ticker]
    missing = [t for t in candidates if t not in sector_cache]
    if missing:
        batch_result = get_sector_info_batch(missing)
        for sym, info in batch_result.items():
            sector_cache[sym] = info

    exact_matches: List[Dict[str, Any]] = []
    sector_only_matches: List[Dict[str, Any]] = []

    for candidate_ticker in candidates:
        candidate_info = sector_cache.get(candidate_ticker)
        if not candidate_info:
            continue
        candidate_sector = candidate_info.get("sector")
        candidate_industry = candidate_info.get("industry")
        sector_match = bool(target_sector and candidate_sector == target_sector)
        industry_match = bool(target_industry and candidate_industry == target_industry)

        row = {
            "ticker": candidate_ticker,
            "name": candidate_info.get("name", candidate_ticker),
            "sector": candidate_sector,
            "industry": candidate_industry,
            "market_cap": candidate_info.get("market_cap"),
            "current_price": None,
            "change_percent": None,
            "trailing_pe": candidate_info.get("trailing_pe"),
            "forward_pe": candidate_info.get("forward_pe"),
            "trailing_eps": candidate_info.get("trailing_eps"),
            "forward_eps": candidate_info.get("forward_eps"),
            "ebitda": candidate_info.get("ebitda"),
            "revenue": candidate_info.get("revenue"),
            "profit_margin": candidate_info.get("profit_margin"),
            "gross_margin": candidate_info.get("gross_margin"),
            "operating_margin": candidate_info.get("operating_margin"),
            "ebitda_margin": candidate_info.get("ebitda_margin"),
            "beta": candidate_info.get("beta"),
            "dividend_yield": candidate_info.get("dividend_yield"),
            "fifty_two_week_high": candidate_info.get("fifty_two_week_high"),
            "fifty_two_week_low": candidate_info.get("fifty_two_week_low"),
            "target_mean_price": candidate_info.get("target_mean_price"),
            "recommendation_key": candidate_info.get("recommendation_key"),
        }
        if sector_match and industry_match:
            exact_matches.append(row)
        elif sector_match:
            sector_only_matches.append(row)

    exact_matches.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    sector_only_matches.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    safe_offset = max(0, int(offset))
    safe_limit = max(1, int(limit))
    fallback_threshold = 10
    use_sector_fallback = len(exact_matches) < fallback_threshold
    if use_sector_fallback:
        all_matches = exact_matches + sector_only_matches
        match_type = "sector_only" if all_matches else "no_matches"
    else:
        all_matches = exact_matches
        match_type = "sector_and_industry" if all_matches else "no_matches"

    if target_industry:
        all_matches.sort(
            key=lambda x: (
                0 if x.get("industry") == target_industry else 1,
                -(x.get("market_cap") or 0),
                x.get("ticker", ""),
            )
        )

    total_count = len(all_matches)
    similar_stocks = all_matches[safe_offset : safe_offset + safe_limit]

    if get_quotes_batch and similar_stocks:
        symbols = [r["ticker"] for r in similar_stocks if r.get("ticker")]
        if symbols:
            quotes = get_quotes_batch(symbols)
            for row in similar_stocks:
                sym = row.get("ticker")
                if not sym:
                    continue
                q = quotes.get(sym) if isinstance(quotes, dict) else None
                if isinstance(q, dict):
                    row["current_price"] = q.get("current_price")
                    row["change_percent"] = q.get("daily_change_percent")

    return {
        "ticker": ticker,
        "sector": target_sector,
        "industry": target_industry,
        "similar_tickers": similar_stocks,
        "count": len(similar_stocks),
        "total_count": total_count,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(similar_stocks) < total_count,
        "match_type": match_type,
        "method": "yahooquery_batch",
    }

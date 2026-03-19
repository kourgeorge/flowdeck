"""
Single algorithmic step for the User Daily Brief: build DigestContext from portfolio and data services.

Loads portfolio tickers, fetches base market data, ranks by attention score, fetches detailed
evidence and platform reports for priority tickers, fetches market context, and builds
sector/peer context. All deterministic (no LLM). On partial failure for a ticker, that key
is left empty so agents can use tools to fill gaps.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.processing import extract_ticker_events, parse_rsi_indicator_data

from .state import DigestContext

logger = logging.getLogger(__name__)

# Default attention weights: absolute 1d return, 5d return, abnormal flag, has recent news
W_EVENT, W1, W2, W3, W4 = 1.0, 0.2, 0.1, 0.15, 0.1
ABNORMAL_THRESHOLD_PCT = 3.0  # |1d return| > this (%) -> abnormal_signal True


def _ensure_backend_on_path() -> None:
    if "backend" in [os.path.basename(p) for p in sys.path]:
        return
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_dir = os.path.join(repo_root, "backend")
    if os.path.isdir(backend_dir) and backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def _load_portfolio_tickers(user_id: int, db: Any) -> List[str]:
    _ensure_backend_on_path()
    from models.db_models import Subscription  # type: ignore[import-untyped]
    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.ticker)
        .all()
    )
    return [s.ticker.upper() for s in subs]


def _get_user_context_snapshot(user_id: int, db: Any) -> Optional[str]:
    try:
        from ai_engine.agent.tools.user_context import _get_user_context
        return _get_user_context(user_id, db)
    except Exception:
        return None


def _load_ohlcv_history(
    fetcher: Any,
    tickers: List[str],
    *,
    period: str = "1y",
    interval: str = "1d",
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch daily OHLCV history per ticker for deterministic event extraction."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for ticker in tickers:
        try:
            hist = fetcher.get_historical(ticker, period=period, interval=interval)
            rows = (hist or {}).get("data") or []
            out[ticker] = [row for row in rows if isinstance(row, dict)]
        except Exception as e:
            logger.debug("Historical data for %s: %s", ticker, e)
            out[ticker] = []
    return out


def _load_future_events(fetcher: Any, tickers: List[str]) -> Dict[str, Any]:
    """Fetch structured future-event payloads when available."""
    out: Dict[str, Any] = {}
    for ticker in tickers:
        try:
            getter = getattr(fetcher, "get_future_events", None)
            if getter is None:
                out[ticker] = {}
                continue
            out[ticker] = getter(ticker) or {}
        except Exception as e:
            logger.debug("Future events for %s: %s", ticker, e)
            out[ticker] = {}
    return out


def _load_insider_transactions(fetcher: Any, tickers: List[str], limit: int = 20) -> Dict[str, Any]:
    """Fetch normalized insider transaction payloads per ticker."""
    out: Dict[str, Any] = {}
    for ticker in tickers:
        try:
            out[ticker] = fetcher.get_insider_transactions(ticker, limit=limit) or {}
        except Exception as e:
            logger.debug("Insider transactions for %s: %s", ticker, e)
            out[ticker] = {}
    return out


def _load_rsi_maps(
    fetcher: Any,
    tickers: List[str],
    *,
    as_of_date: str,
    look_back_days: int = 60,
) -> Dict[str, Dict[str, float]]:
    """Fetch and parse RSI series per ticker when the backend fetcher supports indicators."""
    out: Dict[str, Dict[str, float]] = {}
    getter = getattr(fetcher, "get_indicators", None)
    if getter is None:
        return {ticker: {} for ticker in tickers}
    for ticker in tickers:
        try:
            raw = getter(ticker, "rsi", as_of_date, look_back_days)
            out[ticker] = parse_rsi_indicator_data(raw)
        except Exception as e:
            logger.debug("RSI data for %s: %s", ticker, e)
            out[ticker] = {}
    return out


def _compute_returns_and_abnormal(
    history_map: Dict[str, List[Dict[str, Any]]],
    tickers: List[str],
    span_trading_days: Optional[int] = None,
) -> tuple[
    Dict[str, Optional[float]],
    Dict[str, Optional[float]],
    Dict[str, Optional[float]],
    Dict[str, bool],
]:
    """Returns (returns_1d, returns_5d, returns_span, abnormal_signal). returns_span only set when span_trading_days is provided (e.g. 7 for weekly)."""
    returns_1d: Dict[str, Optional[float]] = {}
    returns_5d: Dict[str, Optional[float]] = {}
    returns_span: Dict[str, Optional[float]] = {}
    abnormal_signal: Dict[str, bool] = {}
    need_span = span_trading_days is not None and span_trading_days >= 1
    min_bars = 6 if not need_span else max(6, span_trading_days + 1)

    for ticker in tickers:
        try:
            data = history_map.get(ticker) or []
            if len(data) < min_bars:
                returns_1d[ticker] = None
                returns_5d[ticker] = None
                if need_span:
                    returns_span[ticker] = None
                abnormal_signal[ticker] = False
                continue
            # Assume ascending date (oldest first); last = latest
            closes = [float(d["close"]) for d in data if d.get("close") is not None]
            if not closes:
                returns_1d[ticker] = None
                returns_5d[ticker] = None
                if need_span:
                    returns_span[ticker] = None
                abnormal_signal[ticker] = False
                continue
            c_now = closes[-1]
            c_1d = closes[-2] if len(closes) >= 2 else c_now
            c_5d = closes[-6] if len(closes) >= 6 else (closes[0] if closes else c_now)
            r1 = (c_now - c_1d) / c_1d * 100.0 if c_1d and c_1d != 0 else None
            r5 = (c_now - c_5d) / c_5d * 100.0 if c_5d and c_5d != 0 else None
            returns_1d[ticker] = r1
            returns_5d[ticker] = r5
            if need_span and len(closes) >= span_trading_days + 1:
                c_start = closes[-(span_trading_days + 1)]
                r_span = (c_now - c_start) / c_start * 100.0 if c_start and c_start != 0 else None
                returns_span[ticker] = r_span
            elif need_span:
                returns_span[ticker] = None
            abnormal_signal[ticker] = r1 is not None and abs(r1) > ABNORMAL_THRESHOLD_PCT
        except Exception as e:
            logger.debug("Returns for %s: %s", ticker, e)
            returns_1d[ticker] = None
            returns_5d[ticker] = None
            if need_span:
                returns_span[ticker] = None
            abnormal_signal[ticker] = False
    return returns_1d, returns_5d, returns_span, abnormal_signal


def _has_recent_news(fetcher: Any, tickers: List[str], lookback_days: int = 2) -> Dict[str, bool]:
    out: Dict[str, bool] = {t: False for t in tickers}
    try:
        batch = fetcher.get_news_batch(tickers, lookback_days=lookback_days)
        articles = (batch or {}).get("articles") or []
        for a in articles:
            for t in (a.get("tickers") or []):
                t = t.upper() if isinstance(t, str) else t
                if t in out:
                    out[t] = True
    except Exception as e:
        logger.debug("has_recent_news: %s", e)
    return out


def _rank_tickers(
    tickers: List[str],
    event_scores: Dict[str, float],
    returns_1d: Dict[str, Optional[float]],
    returns_5d: Dict[str, Optional[float]],
    abnormal_signal: Dict[str, bool],
    has_news: Dict[str, bool],
    max_n: int,
    returns_span: Optional[Dict[str, Optional[float]]] = None,
) -> tuple[Dict[str, float], List[str]]:
    """When returns_span is provided (e.g. for weekly), rank by span return + news; otherwise use 1d/5d."""
    scores: Dict[str, float] = {}
    if returns_span:
        for t in tickers:
            ev = event_scores.get(t) or 0.0
            r_span = (returns_span.get(t) or 0.0) if returns_span else 0.0
            sc = W_EVENT * ev + 0.2 * abs(r_span) + (0.5 if has_news.get(t) else 0)
            scores[t] = sc
    else:
        for t in tickers:
            ev = event_scores.get(t) or 0.0
            r1 = returns_1d.get(t) or 0.0
            r5 = returns_5d.get(t) or 0.0
            sc = W_EVENT * ev + W1 * abs(r1) + W2 * abs(r5) + (W3 if abnormal_signal.get(t) else 0) + (W4 if has_news.get(t) else 0)
            scores[t] = sc
    sorted_tickers = sorted(scores.keys(), key=lambda x: -scores[x])
    return scores, sorted_tickers[:max_n]


def _fetch_global_news(digest_date: str, lookback_days: int = 7) -> Any:
    try:
        from ai_engine.tradingagents.datasources.info_service_client import (
            get_global_news,
            is_configured,
        )
        if not is_configured():
            return None
        return get_global_news(digest_date, lookback_days, 10, None)
    except Exception as e:
        logger.debug("Global news: %s", e)
        return None


def _fetch_web_snippet() -> Optional[str]:
    try:
        from ai_engine.agent.tools.web_search import WebSearchTool
        from ai_engine.agent.tool import ExecutionContext
        tool = WebSearchTool()
        result = tool.execute(ExecutionContext(), query="market today Fed macro")
        if result.ok and result.data:
            return str(result.data)[:2000]
    except Exception as e:
        logger.debug("Web search snippet: %s", e)
    return None


def _fetch_market_context(fetcher: Any, digest_date: str, lookback_days: int) -> tuple[Dict[str, Any], Any, Optional[str]]:
    """Fetch market-wide context independent of the user's subscribed tickers."""
    try:
        market_movers = fetcher.get_daily_market_movers(10)
    except Exception:
        market_movers = {}
    global_news = _fetch_global_news(digest_date, lookback_days=min(lookback_days + 5, 14))
    web_search_snippet = _fetch_web_snippet()
    return market_movers, global_news, web_search_snippet


def _extract_market_focus_rows(market_movers: Dict[str, Any], max_n: int) -> List[Dict[str, Any]]:
    """Select fallback focus rows from market movers when the user has no portfolio."""
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("gainers", "losers", "most_active"):
        for row in (market_movers or {}).get(key) or []:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            rows.append(row)
            seen.add(symbol)
    rows.sort(
        key=lambda row: abs(float(row.get("regularMarketChangePercent") or 0.0)),
        reverse=True,
    )
    return rows[:max_n]


def _quote_from_market_mover(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a market mover row to the quote-like shape used by the digest UI."""
    return {
        "current_price": row.get("regularMarketPrice"),
        "daily_change": row.get("regularMarketChange"),
        "daily_change_percent": row.get("regularMarketChangePercent"),
        "name": row.get("shortName"),
    }


def build_digest_context(
    user_id: int,
    digest_date: str,
    max_priority_tickers: int,
    db: Any,
    fetcher: Optional[Any] = None,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    span_trading_days: Optional[int] = None,
) -> DigestContext:
    """
    Build the full DigestContext: portfolio, base data, ranking, evidence, reports, market context, sector/peer.

    If fetcher is None, backend is used (get_info_fetcher()). On partial failure for a ticker,
    that ticker's keys are left empty/None; agents can use tools to fill gaps.

    When start_date/end_date or span_trading_days are set (e.g. for weekly brief), news lookback
    and ranking use the span; returns_span is computed for the span period.
    """
    _ensure_backend_on_path()
    if fetcher is None:
        from services.info_fetcher import get_info_fetcher  # type: ignore[import-untyped]
        fetcher = get_info_fetcher()

    # Market-wide context should exist even when the user has no subscribed tickers.
    if span_trading_days is not None and span_trading_days > 0:
        lookback_days = min(span_trading_days + 2, 31)
    else:
        lookback_days = 2
    market_movers, global_news, web_search_snippet = _fetch_market_context(fetcher, digest_date, lookback_days)

    tickers = _load_portfolio_tickers(user_id, db)
    if not tickers:
        user_context_snapshot = _get_user_context_snapshot(user_id, db)
        fallback_rows = _extract_market_focus_rows(market_movers, max_priority_tickers)
        priority_tickers = [
            str(row.get("symbol") or "").strip().upper()
            for row in fallback_rows
            if str(row.get("symbol") or "").strip()
        ]
        quotes = {
            ticker: _quote_from_market_mover(row)
            for ticker, row in zip(priority_tickers, fallback_rows)
        }
        returns_1d = {
            ticker: row.get("regularMarketChangePercent")
            for ticker, row in zip(priority_tickers, fallback_rows)
        }
        abnormal_signal = {
            ticker: abs(float(returns_1d.get(ticker) or 0.0)) > ABNORMAL_THRESHOLD_PCT
            for ticker in priority_tickers
        }
        attention_scores = {
            ticker: abs(float(returns_1d.get(ticker) or 0.0))
            for ticker in priority_tickers
        }
        ohlcv_history = _load_ohlcv_history(fetcher, priority_tickers)
        future_events = _load_future_events(fetcher, priority_tickers)
        insider = _load_insider_transactions(fetcher, priority_tickers, limit=20)
        rsi_maps = _load_rsi_maps(fetcher, priority_tickers, as_of_date=digest_date)

        news_lookback = min(lookback_days + 5, 31)
        news: Dict[str, Any] = {}
        fundamentals: Dict[str, Any] = {}
        analyst_rec: Dict[str, Any] = {}
        indicators: Dict[str, Any] = {}
        event_summaries: Dict[str, Any] = {}
        event_scores: Dict[str, float] = {}
        for t in priority_tickers:
            try:
                news[t] = fetcher.get_news(t, lookback_days=news_lookback)
            except Exception:
                news[t] = {}
            try:
                fundamentals[t] = fetcher.get_fundamentals(t)
            except Exception:
                fundamentals[t] = {}
            try:
                analyst_rec[t] = fetcher.get_analyst_recommendations(t)
            except Exception:
                analyst_rec[t] = {}
            event_summary = extract_ticker_events(
                t,
                bars=ohlcv_history.get(t) or [],
                as_of_date=digest_date,
                future_events=future_events.get(t),
                insider_transactions=insider.get(t),
                rsi_data=rsi_maps.get(t),
                start_date=start_date,
                end_date=end_date,
            )
            event_summaries[t] = event_summary
            event_scores[t] = event_summary.event_score

        for ticker, score in event_scores.items():
            attention_scores[ticker] = attention_scores.get(ticker, 0.0) + score

        from services.report_service import ReportService  # type: ignore[import-untyped]
        from services.share_service import get_share_url  # type: ignore[import-untyped]
        report_svc = ReportService()
        platform_reports: Dict[str, Dict[str, Any]] = {}
        share_urls: Dict[str, str] = {}
        for t in priority_tickers:
            try:
                latest = report_svc.get_latest_execution_for_ticker(t)
                if latest:
                    ar_id, _ = latest
                    platform_reports[t] = report_svc.get_reports_with_scores(ar_id)
                    url = get_share_url(ar_id)
                    if url:
                        share_urls[t] = url
                else:
                    platform_reports[t] = {}
            except Exception:
                platform_reports[t] = {}

        try:
            company_batch = fetcher.get_company_info_batch(priority_tickers)
        except Exception:
            company_batch = {}
        sector_industry: Dict[str, Dict[str, str]] = {}
        for t in priority_tickers:
            info = (company_batch or {}).get(t) or {}
            sector_industry[t] = {
                "sector": (info.get("sector") or "N/A"),
                "industry": (info.get("industry") or "N/A"),
            }

        peer_tickers = {t: [] for t in priority_tickers}
        peer_quotes: Dict[str, Any] = {}

        logger.info("Digest: no portfolio tickers for user_id=%s", user_id)
        return DigestContext(
            tickers=[],
            user_context_snapshot=user_context_snapshot,
            priority_tickers=priority_tickers,
            attention_scores=attention_scores,
            quotes=quotes,
            ohlcv_history=ohlcv_history,
            returns_1d=returns_1d,
            returns_5d={},
            returns_span={},
            abnormal_signal=abnormal_signal,
            event_summaries=event_summaries,
            event_scores=event_scores,
            news=news,
            fundamentals=fundamentals,
            analyst_rec=analyst_rec,
            insider=insider,
            future_events=future_events,
            indicators=indicators,
            platform_reports=platform_reports,
            share_urls=share_urls,
            sector_industry=sector_industry,
            peer_tickers=peer_tickers,
            peer_quotes=peer_quotes,
            market_movers=market_movers,
            global_news=global_news,
            web_search_snippet=web_search_snippet,
        )

    user_context_snapshot = _get_user_context_snapshot(user_id, db)

    # Base market data (returns_span when span_trading_days e.g. 7 for weekly)
    quotes = fetcher.get_quotes_batch(tickers) or {}
    ohlcv_history = _load_ohlcv_history(fetcher, tickers)
    returns_1d, returns_5d, returns_span, abnormal_signal = _compute_returns_and_abnormal(
        ohlcv_history, tickers, span_trading_days=span_trading_days
    )
    future_events = _load_future_events(fetcher, tickers)
    insider = _load_insider_transactions(fetcher, tickers, limit=20)
    rsi_maps = _load_rsi_maps(fetcher, tickers, as_of_date=digest_date)
    event_summaries = {
        ticker: extract_ticker_events(
            ticker,
            bars=ohlcv_history.get(ticker) or [],
            as_of_date=digest_date,
            future_events=future_events.get(ticker),
            insider_transactions=insider.get(ticker),
            rsi_data=rsi_maps.get(ticker),
            start_date=start_date,
            end_date=end_date,
        )
        for ticker in tickers
    }
    event_scores = {ticker: summary.event_score for ticker, summary in event_summaries.items()}

    # Rank: use span return + news when span; else 1d/5d/abnormal/news
    has_news = _has_recent_news(fetcher, tickers, lookback_days=lookback_days)
    attention_scores, priority_tickers = _rank_tickers(
        tickers,
        event_scores,
        returns_1d,
        returns_5d,
        abnormal_signal,
        has_news,
        max_priority_tickers,
        returns_span=returns_span if returns_span else None,
    )
    logger.info("Digest: context built, %d priority tickers: %s", len(priority_tickers), priority_tickers)

    # Per-priority evidence; news lookback matches span
    news_lookback = min(lookback_days + 5, 31)  # slightly wider for per-ticker news
    news: Dict[str, Any] = {}
    fundamentals: Dict[str, Any] = {}
    analyst_rec: Dict[str, Any] = {}
    indicators: Dict[str, Any] = {}  # backend has no get_indicators; agents have tool
    priority_future_events: Dict[str, Any] = {}

    for t in priority_tickers:
        try:
            news[t] = fetcher.get_news(t, lookback_days=news_lookback)
        except Exception:
            news[t] = {}
        try:
            fundamentals[t] = fetcher.get_fundamentals(t)
        except Exception:
            fundamentals[t] = {}
        try:
            analyst_rec[t] = fetcher.get_analyst_recommendations(t)
        except Exception:
            analyst_rec[t] = {}
        priority_future_events[t] = future_events.get(t) or {}
    insider = {ticker: insider.get(ticker) or {} for ticker in priority_tickers}

    # Platform reports and share URLs
    from services.report_service import ReportService  # type: ignore[import-untyped]
    from services.share_service import get_share_url  # type: ignore[import-untyped]
    report_svc = ReportService()
    platform_reports: Dict[str, Dict[str, Any]] = {}
    share_urls: Dict[str, str] = {}
    for t in priority_tickers:
        try:
            latest = report_svc.get_latest_execution_for_ticker(t)
            if latest:
                ar_id, _ = latest
                platform_reports[t] = report_svc.get_reports_with_scores(ar_id)
                url = get_share_url(ar_id)
                if url:
                    share_urls[t] = url
            else:
                platform_reports[t] = {}
        except Exception:
            platform_reports[t] = {}

    # Sector/peer
    try:
        company_batch = fetcher.get_company_info_batch(priority_tickers)
    except Exception:
        company_batch = {}
    sector_industry: Dict[str, Dict[str, str]] = {}
    for t in priority_tickers:
        info = (company_batch or {}).get(t) or {}
        sector_industry[t] = {
            "sector": (info.get("sector") or "N/A"),
            "industry": (info.get("industry") or "N/A"),
        }

    # Peer set: same sector from portfolio + market movers
    all_candidates = list(tickers)
    try:
        movers = (market_movers or {}).get("gainers") or []
        movers += (market_movers or {}).get("losers") or []
        for m in movers:
            sym = (m.get("symbol") or m.get("ticker") or "").upper()
            if sym and sym not in all_candidates:
                all_candidates.append(sym)
    except Exception:
        pass

    sector_to_tickers: Dict[str, List[str]] = {}
    for t, si in sector_industry.items():
        sec = (si.get("sector") or "N/A").strip() or "N/A"
        sector_to_tickers.setdefault(sec, []).append(t)

    peer_tickers: Dict[str, List[str]] = {}
    for t in priority_tickers:
        sec = (sector_industry.get(t) or {}).get("sector") or "N/A"
        peers = [p for p in (sector_to_tickers.get(sec) or []) if p != t][:5]
        peer_tickers[t] = peers

    all_peers = list({p for peers in peer_tickers.values() for p in peers})
    peer_quotes_raw = fetcher.get_quotes_batch(all_peers) if all_peers else {}
    peer_quotes: Dict[str, Any] = dict(peer_quotes_raw or {})

    return DigestContext(
        tickers=tickers,
        user_context_snapshot=user_context_snapshot,
        priority_tickers=priority_tickers,
        attention_scores=attention_scores,
        quotes=quotes,
        ohlcv_history=ohlcv_history,
        returns_1d=returns_1d,
        returns_5d=returns_5d,
        returns_span=returns_span or {},
        abnormal_signal=abnormal_signal,
        event_summaries=event_summaries,
        event_scores=event_scores,
        news=news,
        fundamentals=fundamentals,
        analyst_rec=analyst_rec,
        insider=insider,
        future_events=priority_future_events,
        indicators=indicators,
        platform_reports=platform_reports,
        share_urls=share_urls,
        sector_industry=sector_industry,
        peer_tickers=peer_tickers,
        peer_quotes=peer_quotes,
        market_movers=market_movers,
        global_news=global_news,
        web_search_snippet=web_search_snippet,
    )

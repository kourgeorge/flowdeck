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

from .state import DigestContext

logger = logging.getLogger(__name__)

# Default attention weights: absolute 1d return, 5d return, abnormal flag, has recent news
W1, W2, W3, W4 = 0.4, 0.3, 0.2, 0.1
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


def _compute_returns_and_abnormal(
    fetcher: Any,
    tickers: List[str],
) -> tuple[Dict[str, Optional[float]], Dict[str, Optional[float]], Dict[str, bool]]:
    returns_1d: Dict[str, Optional[float]] = {}
    returns_5d: Dict[str, Optional[float]] = {}
    abnormal_signal: Dict[str, bool] = {}
    for ticker in tickers:
        try:
            hist = fetcher.get_historical(ticker, period="1mo", interval="1d")
            data = (hist or {}).get("data") or []
            if len(data) < 6:
                returns_1d[ticker] = None
                returns_5d[ticker] = None
                abnormal_signal[ticker] = False
                continue
            # data is newest first? Check: yfinance history often returns oldest first
            closes = [float(d["close"]) for d in data if d.get("close") is not None]
            if not closes:
                returns_1d[ticker] = None
                returns_5d[ticker] = None
                abnormal_signal[ticker] = False
                continue
            # Assume ascending date (oldest first); last = latest
            c_now = closes[-1]
            c_1d = closes[-2] if len(closes) >= 2 else c_now
            c_5d = closes[-6] if len(closes) >= 6 else (closes[0] if closes else c_now)
            r1 = (c_now - c_1d) / c_1d * 100.0 if c_1d and c_1d != 0 else None
            r5 = (c_now - c_5d) / c_5d * 100.0 if c_5d and c_5d != 0 else None
            returns_1d[ticker] = r1
            returns_5d[ticker] = r5
            abnormal_signal[ticker] = r1 is not None and abs(r1) > ABNORMAL_THRESHOLD_PCT
        except Exception as e:
            logger.debug("Returns for %s: %s", ticker, e)
            returns_1d[ticker] = None
            returns_5d[ticker] = None
            abnormal_signal[ticker] = False
    return returns_1d, returns_5d, abnormal_signal


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
    returns_1d: Dict[str, Optional[float]],
    returns_5d: Dict[str, Optional[float]],
    abnormal_signal: Dict[str, bool],
    has_news: Dict[str, bool],
    max_n: int,
) -> tuple[Dict[str, float], List[str]]:
    scores: Dict[str, float] = {}
    for t in tickers:
        r1 = returns_1d.get(t) or 0.0
        r5 = returns_5d.get(t) or 0.0
        sc = W1 * abs(r1) + W2 * abs(r5) + (W3 if abnormal_signal.get(t) else 0) + (W4 if has_news.get(t) else 0)
        scores[t] = sc
    sorted_tickers = sorted(scores.keys(), key=lambda x: -scores[x])
    return scores, sorted_tickers[:max_n]


def _fetch_global_news(digest_date: str) -> Any:
    try:
        from ai_engine.tradingagents.dataflows.interface import route_to_vendor
        return route_to_vendor("get_global_news", digest_date, 7, 10, None)
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


def build_digest_context(
    user_id: int,
    digest_date: str,
    max_priority_tickers: int,
    db: Any,
    fetcher: Optional[Any] = None,
) -> DigestContext:
    """
    Build the full DigestContext: portfolio, base data, ranking, evidence, reports, market context, sector/peer.

    If fetcher is None, backend is used (get_info_fetcher()). On partial failure for a ticker,
    that ticker's keys are left empty/None; agents can use tools to fill gaps.
    """
    _ensure_backend_on_path()
    if fetcher is None:
        from services.info_fetcher import get_info_fetcher  # type: ignore[import-untyped]
        fetcher = get_info_fetcher()

    tickers = _load_portfolio_tickers(user_id, db)
    if not tickers:
        logger.info("Digest: no portfolio tickers for user_id=%s", user_id)
        return DigestContext(
            tickers=[],
            user_context_snapshot=_get_user_context_snapshot(user_id, db),
            priority_tickers=[],
            attention_scores={},
        )

    user_context_snapshot = _get_user_context_snapshot(user_id, db)

    # Base market data
    quotes = fetcher.get_quotes_batch(tickers) or {}
    returns_1d, returns_5d, abnormal_signal = _compute_returns_and_abnormal(fetcher, tickers)

    # Rank
    has_news = _has_recent_news(fetcher, tickers, lookback_days=2)
    attention_scores, priority_tickers = _rank_tickers(
        tickers, returns_1d, returns_5d, abnormal_signal, has_news, max_priority_tickers
    )
    logger.info("Digest: context built, %d priority tickers: %s", len(priority_tickers), priority_tickers)

    # Per-priority evidence
    news: Dict[str, Any] = {}
    fundamentals: Dict[str, Any] = {}
    analyst_rec: Dict[str, Any] = {}
    insider: Dict[str, Any] = {}
    indicators: Dict[str, Any] = {}  # backend has no get_indicators; agents have tool

    for t in priority_tickers:
        try:
            news[t] = fetcher.get_news(t, lookback_days=7)
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
        try:
            insider[t] = fetcher.get_insider_transactions(t, limit=20)
        except Exception:
            insider[t] = {}

    # Platform reports
    from services.report_service import ReportService  # type: ignore[import-untyped]
    report_svc = ReportService()
    platform_reports: Dict[str, Dict[str, Any]] = {}
    for t in priority_tickers:
        try:
            latest = report_svc.get_latest_analysis_run(t)
            if latest:
                ar_id, _ = latest
                platform_reports[t] = report_svc.get_reports_with_scores(t, ar_id)
            else:
                platform_reports[t] = {}
        except Exception:
            platform_reports[t] = {}

    # Market context
    try:
        market_movers = fetcher.get_daily_market_movers(10)
    except Exception:
        market_movers = {}
    global_news = _fetch_global_news(digest_date)
    web_search_snippet = _fetch_web_snippet()

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
        returns_1d=returns_1d,
        returns_5d=returns_5d,
        abnormal_signal=abnormal_signal,
        news=news,
        fundamentals=fundamentals,
        analyst_rec=analyst_rec,
        insider=insider,
        indicators=indicators,
        platform_reports=platform_reports,
        sector_industry=sector_industry,
        peer_tickers=peer_tickers,
        peer_quotes=peer_quotes,
        market_movers=market_movers,
        global_news=global_news,
        web_search_snippet=web_search_snippet,
    )

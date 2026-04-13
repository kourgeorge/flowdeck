"""
Deterministic candidate discovery: interest cluster, movers filter, event scoring.

Reuses briefing context_builder data loaders (shared infra, not briefing workflow).
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List, Tuple

from ai_engine.tradingagents.agents.utils.trace_utils import make_agent_step
from backend.processing import get_ticker_event_summary

from ai_engine.briefing_agent.context_builder import (
    _load_future_events,
    _load_insider_transactions,
    _load_ohlcv_history,
    _load_rsi_maps,
)
from ai_engine.briefing_agent.state import DigestContext

logger = logging.getLogger(__name__)


def _analyze_interest_cluster(
    sector_industry: Dict[str, Dict[str, str]],
    company_batch: Dict[str, Any],
) -> Dict[str, Any]:
    exchanges: List[str] = []
    sectors: List[str] = []
    industries: List[str] = []

    for ticker, info in company_batch.items():
        exchange = (info.get("exchange") or "").strip()
        if exchange and exchange != "N/A":
            exchanges.append(exchange)

        si = sector_industry.get(ticker) or {}
        sector = (si.get("sector") or "").strip()
        if sector and sector != "N/A":
            sectors.append(sector)

        industry = (si.get("industry") or "").strip()
        if industry and industry != "N/A":
            industries.append(industry)

    exchange_counts = Counter(exchanges)
    sector_counts = Counter(sectors)
    industry_counts = Counter(industries)

    return {
        "exchanges": [ex for ex, _ in exchange_counts.most_common(3)],
        "sectors": [sec for sec, _ in sector_counts.most_common(3)],
        "industries": [ind for ind, _ in industry_counts.most_common(5)],
    }


def _discover_cluster_tickers(
    interest_cluster: Dict[str, Any],
    market_movers: Dict[str, Any],
    portfolio_tickers: List[str],
    fetcher: Any,
    max_candidates: int = 30,
) -> List[str]:
    portfolio_set = {t.upper() for t in portfolio_tickers}
    candidates: List[str] = []
    seen: set[str] = set()

    for key in ("gainers", "losers", "most_active"):
        for mover in (market_movers or {}).get(key) or []:
            if not isinstance(mover, dict):
                continue
            symbol = str(mover.get("symbol") or "").strip().upper()
            if not symbol or symbol in portfolio_set or symbol in seen:
                continue
            candidates.append(symbol)
            seen.add(symbol)
            if len(candidates) >= max_candidates:
                break
        if len(candidates) >= max_candidates:
            break

    if not candidates:
        logger.debug("No candidate tickers found from market movers")
        return []

    try:
        company_info_batch = fetcher.get_company_info_batch(candidates[:50])
    except Exception as e:
        logger.debug("Failed to fetch company info for candidates: %s", e)
        return candidates[:max_candidates]

    cluster_exchanges = set(interest_cluster.get("exchanges") or [])
    cluster_sectors = set(interest_cluster.get("sectors") or [])
    cluster_industries = set(interest_cluster.get("industries") or [])

    filtered: List[tuple[str, int]] = []
    for ticker in candidates:
        info = (company_info_batch or {}).get(ticker) or {}
        exchange = (info.get("exchange") or "").strip()
        sector = (info.get("sector") or "").strip()
        industry = (info.get("industry") or "").strip()

        match_score = 0
        if exchange in cluster_exchanges:
            match_score += 1
        if sector in cluster_sectors:
            match_score += 2
        if industry in cluster_industries:
            match_score += 3

        if match_score > 0:
            filtered.append((ticker, match_score))

    filtered.sort(key=lambda x: -x[1])
    return [ticker for ticker, _ in filtered[:max_candidates]]


def _score_tickers_by_event_activity(
    tickers: List[str],
    fetcher: Any,
    as_of_date: str,
    lookback_days: int = 10,
    max_results: int = 10,
) -> Tuple[List[str], Dict[str, Any], Dict[str, Any]]:
    if not tickers:
        return [], {}, {}

    ohlcv_history = _load_ohlcv_history(fetcher, tickers, period="1y", interval="1d")
    future_events = _load_future_events(fetcher, tickers)
    insider = _load_insider_transactions(fetcher, tickers, limit=20)
    rsi_maps = _load_rsi_maps(fetcher, tickers, as_of_date=as_of_date, look_back_days=60)

    event_summaries: Dict[str, Any] = {}
    event_scores: Dict[str, float] = {}

    for ticker in tickers:
        try:
            summary = get_ticker_event_summary(
                fetcher,
                ticker,
                as_of_date=as_of_date,
                bars=ohlcv_history.get(ticker) or [],
                future_events=future_events.get(ticker),
                insider_transactions=insider.get(ticker),
                rsi_data=rsi_maps.get(ticker),
                history_period="1y",
                history_interval="1d",
                insider_limit=20,
                price_technical_lookback_days=lookback_days,
            )
            event_summaries[ticker] = summary
            event_scores[ticker] = summary.event_score
        except Exception as e:
            logger.debug("Failed to get event summary for %s: %s", ticker, e)
            event_scores[ticker] = 0.0

    sorted_tickers = sorted(event_scores.keys(), key=lambda t: -event_scores[t])
    top_tickers = [t for t in sorted_tickers if event_scores[t] > 0][:max_results]

    if not top_tickers:
        return [], {}, {}

    try:
        company_info = fetcher.get_company_info_batch(top_tickers)
        quotes = fetcher.get_quotes_batch(top_tickers) or {}
    except Exception as e:
        logger.debug("Failed to fetch info for top tickers: %s", e)
        company_info = {}
        quotes = {}

    ticker_info: Dict[str, Dict[str, Any]] = {}
    for ticker in top_tickers:
        info = (company_info or {}).get(ticker) or {}
        ticker_info[ticker] = {
            "sector": info.get("sector") or "N/A",
            "industry": info.get("industry") or "N/A",
            "exchange": info.get("exchange") or "N/A",
            "quote": quotes.get(ticker),
        }

    return top_tickers, event_summaries, ticker_info


def run_deterministic_discovery(
    ctx: DigestContext,
    fetcher: Any,
    digest_date: str,
    lookback_days: int,
) -> Tuple[Dict[str, Any], List[str], Dict[str, Any], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (interest_cluster, discovered_tickers, event_summaries, ticker_info, agent_steps).
    event_summaries maps ticker -> TickerEventSummary.
    """
    steps: List[Dict[str, Any]] = []

    if not ctx or not ctx.tickers:
        steps.append(
            make_agent_step(
                agent="Stocks Discovery (data)",
                phase="discovery",
                kind="analysis",
                status="skipped",
                summary="Stocks discovery skipped",
                output_preview="No portfolio tickers; interest-cluster discovery not applicable.",
            )
        )
        return {}, [], {}, {}, steps

    try:
        company_batch = fetcher.get_company_info_batch(ctx.priority_tickers)
    except Exception:
        company_batch = {}

    interest_cluster = _analyze_interest_cluster(ctx.sector_industry, company_batch or {})

    if not (interest_cluster.get("sectors") or interest_cluster.get("industries")):
        steps.append(
            make_agent_step(
                agent="Stocks Discovery (data)",
                phase="discovery",
                kind="analysis",
                status="completed",
                summary="Stocks discovery: no sector/industry cluster to match",
                output_preview={"interest_cluster": interest_cluster},
            )
        )
        return interest_cluster, [], {}, {}, steps

    candidates = _discover_cluster_tickers(
        interest_cluster,
        ctx.market_movers,
        ctx.tickers,
        fetcher,
        max_candidates=30,
    )

    if not candidates:
        steps.append(
            make_agent_step(
                agent="Stocks Discovery (data)",
                phase="discovery",
                kind="analysis",
                status="completed",
                summary="Stocks discovery: no cluster-aligned candidates from market movers",
                output_preview={"interest_cluster": interest_cluster},
            )
        )
        return interest_cluster, [], {}, {}, steps

    discovered_tickers, discovered_ticker_events, discovered_ticker_info = _score_tickers_by_event_activity(
        candidates,
        fetcher,
        digest_date,
        lookback_days=lookback_days,
        max_results=10,
    )

    if discovered_tickers:
        top_event_scores: Dict[str, float] = {}
        for ticker in discovered_tickers[:5]:
            ev = discovered_ticker_events.get(ticker)
            top_event_scores[ticker] = float(ev.event_score) if ev is not None else 0.0
        steps.append(
            make_agent_step(
                agent="Stocks Discovery (data)",
                phase="discovery",
                kind="analysis",
                status="completed",
                summary=(
                    f"Ranked {len(discovered_tickers)} non-portfolio tickers by deterministic event activity"
                ),
                output_preview={
                    "interest_cluster": interest_cluster,
                    "discovered_count": len(discovered_tickers),
                    "discovered_tickers": discovered_tickers,
                    "top_event_scores": top_event_scores,
                },
            )
        )
    else:
        steps.append(
            make_agent_step(
                agent="Stocks Discovery (data)",
                phase="discovery",
                kind="analysis",
                status="completed",
                summary="Stocks discovery: no candidates exceeded event-activity threshold",
                output_preview={
                    "interest_cluster": interest_cluster,
                    "candidates_scored": len(candidates),
                },
            )
        )

    return interest_cluster, discovered_tickers, discovered_ticker_events, discovered_ticker_info, steps

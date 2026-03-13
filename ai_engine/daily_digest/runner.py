"""
Runner for the User Daily Brief workflow: build context -> Ticker Interpreter -> Market Interpreter -> Narrative Writer.

Single callable run_digest(user_id, digest_date, db, config) for API or cron integration.
Uses ai_engine.llm_provider for LLM access (same as chat and analysis services).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ai_engine.llm_provider import get_config_from_env, get_llm

from .context_builder import build_digest_context
from .agents import run_ticker_interpreter, run_market_interpreter, run_narrative_writer
from .state import DigestWorkflowState, DigestResult

logger = logging.getLogger(__name__)


def run_digest(
    user_id: int,
    digest_date: str,
    db: Any,
    config: Optional[Dict[str, Any]] = None,
    *,
    max_priority_tickers: int = 5,
    fetcher: Optional[Any] = None,
) -> DigestResult:
    """
    Run the full User Daily Brief pipeline and return a DigestResult.

    Steps:
    1. Build DigestContext (algorithmic: portfolio, base data, rank, evidence, reports, market, sector/peer).
    2. If no portfolio tickers, return a minimal result.
    3. Ticker Interpreter (per priority ticker).
    4. Market Interpreter.
    5. Narrative Writer.

    Args:
        user_id: User ID for portfolio and preferences.
        digest_date: Date for the brief (YYYY-MM-DD).
        db: Database session (for loading subscriptions and report service).
        config: Optional config overrides (llm_provider, deep_think_llm, quick_think_llm, etc.).
        max_priority_tickers: Max number of tickers to analyze in depth (default 5).
        fetcher: Optional data fetcher (if None, backend get_info_fetcher() is used).

    Returns:
        DigestResult with narrative, what_to_watch, digest_date, priority_tickers.
    """
    config = config or {}
    # Env-first config (same as chat_service), then overrides from config
    cfg = {**get_config_from_env(), **config}

    state = DigestWorkflowState(
        user_id=user_id,
        digest_date=digest_date,
        max_priority_tickers=max_priority_tickers,
        db=db,
        config=cfg,
    )

    logger.info("Digest: building context for user_id=%s date=%s", user_id, digest_date)
    ctx = build_digest_context(
        user_id=user_id,
        digest_date=digest_date,
        max_priority_tickers=max_priority_tickers,
        db=db,
        fetcher=fetcher,
    )
    state.digest_context = ctx

    if not ctx.tickers:
        return DigestResult(
            narrative="You have no subscribed stocks. Subscribe to tickers on the platform to receive your User Daily Brief.",
            what_to_watch="Add tickers to your portfolio to get personalized insights.",
            digest_date=digest_date,
            priority_tickers=[],
        )

    if not ctx.priority_tickers:
        return DigestResult(
            narrative="Your portfolio had no significant moves or news today. Check back tomorrow for updates.",
            what_to_watch="Watch for earnings and macro events that may affect your holdings.",
            digest_date=digest_date,
            priority_tickers=[],
        )

    llm = get_llm("quick", cfg)

    logger.info("Digest: running ticker interpreter for %d tickers", len(ctx.priority_tickers))
    state.ticker_interpretations = run_ticker_interpreter(state, llm)

    logger.info("Digest: running market interpreter")
    state.market_interpretation = run_market_interpreter(state, llm)

    logger.info("Digest: running narrative writer")
    narrative, what_to_watch = run_narrative_writer(state, llm)
    state.digest_narrative = narrative
    state.what_to_watch = what_to_watch

    return DigestResult(
        narrative=state.digest_narrative,
        what_to_watch=state.what_to_watch,
        digest_date=digest_date,
        priority_tickers=ctx.priority_tickers,
    )

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
from .agents import run_focus_selector, run_ticker_interpreter, run_market_interpreter, run_narrative_writer
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
    user_note: Optional[str] = None,
    narrative_style: Optional[str] = None,
    user_focus_tickers: Optional[list[str]] = None,
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
    if user_note:
        state.user_note = user_note
    if narrative_style:
        state.narrative_style = narrative_style
    if user_focus_tickers:
        # Normalize to upper-case tickers and de-duplicate; leave final validation to focus selector.
        seen: set[str] = set()
        cleaned: list[str] = []
        for t in user_focus_tickers:
            if not t:
                continue
            tu = str(t).upper()
            if tu not in seen:
                cleaned.append(tu)
                seen.add(tu)
        if cleaned:
            state.user_focus_tickers = cleaned

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

    # Track token usage where supported (OpenAI/Azure via LangChain callbacks).
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    try:
        from langchain_community.callbacks import get_openai_callback  # type: ignore[import]
    except Exception:  # pragma: no cover - callback lib may be missing
        get_openai_callback = None  # type: ignore[assignment]

    if get_openai_callback is not None:
        with get_openai_callback() as cb:  # type: ignore[misc]
            logger.info("Digest: running focus selector")
            focus_tickers = run_focus_selector(state, llm)
            if focus_tickers:
                ctx.priority_tickers = focus_tickers

            logger.info("Digest: running ticker interpreter for %d tickers", len(ctx.priority_tickers))
            state.ticker_interpretations = run_ticker_interpreter(state, llm)

            logger.info("Digest: running market interpreter")
            state.market_interpretation = run_market_interpreter(state, llm)

            logger.info("Digest: running narrative writer")
            narrative, what_to_watch = run_narrative_writer(state, llm)

        input_tokens = getattr(cb, "prompt_tokens", None)
        output_tokens = getattr(cb, "completion_tokens", None)
        total_tokens = getattr(cb, "total_tokens", None)
        cost_usd = getattr(cb, "total_cost", None)
    else:
        logger.info("Digest: running focus selector")
        focus_tickers = run_focus_selector(state, llm)
        if focus_tickers:
            ctx.priority_tickers = focus_tickers

        logger.info("Digest: running ticker interpreter for %d tickers", len(ctx.priority_tickers))
        state.ticker_interpretations = run_ticker_interpreter(state, llm)

        logger.info("Digest: running market interpreter")
        state.market_interpretation = run_market_interpreter(state, llm)

        logger.info("Digest: running narrative writer")
        narrative, what_to_watch = run_narrative_writer(state, llm)

    state.digest_narrative = narrative
    state.what_to_watch = what_to_watch

    models_used = {
        "provider": cfg.get("llm_provider"),
        "quick_think": cfg.get("quick_think_llm"),
    }

    return DigestResult(
        narrative=state.digest_narrative,
        what_to_watch=state.what_to_watch,
        digest_date=digest_date,
        priority_tickers=ctx.priority_tickers,
        references=state.references,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        models_used=models_used,
    )

"""
Runner for the User Daily Brief workflow: build context -> Ticker Interpreter -> Market Interpreter -> Narrative Writer.

Single callable run_digest(user_id, digest_date, db, config) for API or cron integration.
Uses ai_engine.llm_provider for LLM access (same as chat and analysis services).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ai_engine.llm_provider import get_config_from_env, get_llm
from backend.processing import build_important_events

from .context_builder import build_digest_context
from .agents import (
    run_focus_selector,
    run_ticker_interpreter,
    run_market_interpreter,
    run_recent_briefs_summarizer,
    run_narrative_writer,
)
from . import prompts
from .state import DigestWorkflowState, DigestResult, HistoricalDigestBrief, SpanType

logger = logging.getLogger(__name__)
_RECENT_BRIEFS_LIMIT = 5


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def _ensure_backend_import_path() -> None:
    try:
        import backend  # noqa: F401
        return
    except Exception:
        pass

    import os
    import sys

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    backend_dir = os.path.join(repo_root, "backend")
    for path in (repo_root, backend_dir):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


def _to_utc_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _load_recent_digest_briefs(
    user_id: int,
    db: Any,
    *,
    limit: int = _RECENT_BRIEFS_LIMIT,
) -> List[HistoricalDigestBrief]:
    """Load the user's most recent stored digests, newest first."""
    if db is None:
        return []

    try:
        _ensure_backend_import_path()
        try:
            from backend.models.db_models import Execution, Report
        except Exception:
            from models.db_models import Execution, Report  # type: ignore[import-not-found]

        rows = (
            db.query(Execution, Report)
            .join(Report, Report.execution_id == Execution.id)
            .filter(
                Execution.execution_type == "daily_digest",
                Execution.subject_type == "user_date",
                Execution.creator_id == user_id,
                Report.report_type == "daily_digest",
            )
            .order_by(Execution.created_at.desc(), Report.created_at.desc(), Execution.id.desc())
            .limit(max(1, int(limit)))
            .all()
        )
        briefs: List[HistoricalDigestBrief] = []
        for execution, report in rows:
            metadata: Dict[str, Any] = {}
            if getattr(report, "metadata_json", None):
                try:
                    metadata = json.loads(report.metadata_json) or {}
                except Exception:
                    metadata = {}

            priority_tickers = metadata.get("priority_tickers") or []
            if not isinstance(priority_tickers, list):
                priority_tickers = []

            narrative = str(getattr(report, "content", "") or "").strip()
            what_to_watch = str(metadata.get("what_to_watch") or "").strip()
            if not narrative and not what_to_watch:
                continue

            briefs.append(
                HistoricalDigestBrief(
                    narrative=narrative,
                    what_to_watch=what_to_watch,
                    digest_date=str(metadata.get("digest_date") or "") or None,
                    created_at=_to_utc_iso(getattr(execution, "created_at", None)),
                    span_type=str(metadata.get("span_type") or "daily"),
                    span_label=str(metadata.get("span_label") or "Daily"),
                    priority_tickers=[str(t) for t in priority_tickers if t],
                )
            )
        return briefs
    except Exception as exc:
        logger.warning("Digest: failed to load recent briefs for user_id=%s: %s", user_id, exc)
        return []


def _format_period_label(span_type: SpanType, start_date: Optional[str], end_date: str) -> str:
    if span_type == "daily":
        return "today"
    if span_type == "weekly":
        return "this week"
    if span_type == "custom" and start_date and end_date:
        try:
            start_d = _parse_date(start_date)
            end_d = _parse_date(end_date)
            return f"{start_d.strftime('%b')} {start_d.day}–{end_d.strftime('%b')} {end_d.day}, {end_d.year}"
        except ValueError:
            return f"{start_date} to {end_date}"
    return "this period"


def _format_span_label(span_type: SpanType, start_date: Optional[str], end_date: str) -> str:
    if span_type == "daily":
        return "Daily"
    if span_type == "weekly":
        return "Weekly"
    if span_type == "custom" and start_date and end_date:
        try:
            start_d = _parse_date(start_date)
            end_d = _parse_date(end_date)
            return f"{start_d.strftime('%b')} {start_d.day}–{end_d.strftime('%b')} {end_d.day}, {end_d.year}"
        except ValueError:
            return f"{start_date} – {end_date}"
    return "Custom"


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
    span_type: SpanType = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> DigestResult:
    """
    Run the full User Daily Brief pipeline and return a DigestResult.

    Steps:
    1. Build DigestContext (algorithmic: portfolio, base data, rank, evidence, reports, market, sector/peer).
    2. Ticker Interpreter (per priority ticker, if any).
    3. Market Interpreter.
    4. Narrative Writer.

    Args:
        user_id: User ID for portfolio and preferences.
        digest_date: Date for the brief (YYYY-MM-DD); for weekly/custom this is the end date.
        db: Database session (for loading subscriptions and report service).
        config: Optional config overrides (llm_provider, deep_think_llm, quick_think_llm, etc.).
        max_priority_tickers: Max number of tickers to analyze in depth (default 5).
        fetcher: Optional data fetcher (if None, backend get_info_fetcher() is used).
        span_type: 'daily', 'weekly', or 'custom'. Weekly = 7 days ending digest_date.
        start_date: Required for custom; for weekly computed from digest_date.
        end_date: Required for custom; for weekly equals digest_date.

    Returns:
        DigestResult with narrative, what_to_watch, digest_date, priority_tickers, span_type, span_label.
    """
    config = config or {}
    cfg = {**get_config_from_env(), **config}

    # Resolve start/end and labels for span
    end_dt = _parse_date(digest_date)
    if span_type == "weekly":
        start_dt = end_dt - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = digest_date
    elif span_type == "custom":
        if not start_date or not end_date:
            span_type = "daily"
            start_date = None
            end_date = digest_date
        else:
            end_date = end_date or digest_date
    else:
        start_date = None
        end_date = digest_date

    period_label = _format_period_label(span_type, start_date, end_date or digest_date)
    span_label = _format_span_label(span_type, start_date, end_date or digest_date)

    span_trading_days: Optional[int] = None
    if span_type == "weekly":
        span_trading_days = 7
    elif span_type == "custom" and start_date and end_date:
        try:
            sd = _parse_date(start_date)
            ed = _parse_date(end_date)
            span_trading_days = max(1, (ed - sd).days)
        except ValueError:
            span_trading_days = None

    state = DigestWorkflowState(
        user_id=user_id,
        digest_date=digest_date,
        span_type=span_type,
        start_date=start_date,
        end_date=end_date,
        period_label=period_label,
        max_priority_tickers=max_priority_tickers,
        db=db,
        config=cfg,
    )
    state.recent_digest_briefs = _load_recent_digest_briefs(user_id, db)
    if user_note:
        state.user_note = user_note
    if narrative_style:
        state.narrative_style = narrative_style
    if user_focus_tickers:
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

    logger.info("Digest: building context for user_id=%s date=%s span=%s", user_id, digest_date, span_type)
    ctx = build_digest_context(
        user_id=user_id,
        digest_date=digest_date,
        max_priority_tickers=max_priority_tickers,
        db=db,
        fetcher=fetcher,
        start_date=start_date,
        end_date=end_date,
        span_trading_days=span_trading_days,
    )
    state.digest_context = ctx
    if not state.narrative_style:
        state.narrative_style = prompts.extract_preferred_style_from_user_context(
            ctx.user_context_snapshot
        )

    quick_llm = get_llm("quick", cfg)
    deep_llm = get_llm("deep", cfg)

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
            focus_tickers = run_focus_selector(state, quick_llm)
            if focus_tickers:
                ctx.priority_tickers = focus_tickers

            logger.info("Digest: running ticker interpreter for %d tickers", len(ctx.priority_tickers))
            state.ticker_interpretations = run_ticker_interpreter(state, quick_llm)

            logger.info("Digest: running market interpreter")
            state.market_interpretation = run_market_interpreter(state, quick_llm)

            logger.info("Digest: summarizing recent briefs")
            state.recent_briefs_summary = run_recent_briefs_summarizer(state, quick_llm)

            logger.info("Digest: running narrative writer")
            narrative, what_to_watch = run_narrative_writer(state, deep_llm)

        input_tokens = getattr(cb, "prompt_tokens", None)
        output_tokens = getattr(cb, "completion_tokens", None)
        total_tokens = getattr(cb, "total_tokens", None)
        cost_usd = getattr(cb, "total_cost", None)
    else:
        logger.info("Digest: running focus selector")
        focus_tickers = run_focus_selector(state, quick_llm)
        if focus_tickers:
            ctx.priority_tickers = focus_tickers

        logger.info("Digest: running ticker interpreter for %d tickers", len(ctx.priority_tickers))
        state.ticker_interpretations = run_ticker_interpreter(state, quick_llm)

        logger.info("Digest: running market interpreter")
        state.market_interpretation = run_market_interpreter(state, quick_llm)

        logger.info("Digest: summarizing recent briefs")
        state.recent_briefs_summary = run_recent_briefs_summarizer(state, quick_llm)

        logger.info("Digest: running narrative writer")
        narrative, what_to_watch = run_narrative_writer(state, deep_llm)

    state.digest_narrative = narrative
    state.what_to_watch = what_to_watch

    # Build per-ticker snapshot for UI: actual price and span-aware percent change.
    focus_snapshot: Dict[str, Any] = {}
    try:
        quotes = getattr(ctx, "quotes", {}) or {}
        returns_1d = getattr(ctx, "returns_1d", {}) or {}
        returns_5d = getattr(ctx, "returns_5d", {}) or {}
        returns_span = getattr(ctx, "returns_span", {}) or {}
        for t in ctx.priority_tickers:
            q = quotes.get(t) or {}
            price = q.get("current_price") or q.get("price")
            name = q.get("name") or q.get("shortName")
            change_pct = None
            if span_type == "daily":
                change_pct = returns_1d.get(t)
            elif span_type == "weekly":
                change_pct = returns_span.get(t)
                if change_pct is None:
                    change_pct = returns_5d.get(t)
            else:
                change_pct = returns_span.get(t)
            focus_snapshot[t] = {
                "name": str(name) if name else None,
                "price": float(price) if price is not None else None,
                "change_pct": float(change_pct) if change_pct is not None else None,
                "span_type": span_type,
            }
    except Exception:
        focus_snapshot = {}

    models_used = {
        "provider": cfg.get("llm_provider"),
        "quick_think": cfg.get("quick_think_llm"),
        "deep_think": cfg.get("deep_think_llm"),
    }
    important_events = build_important_events(
        getattr(ctx, "event_summaries", {}) or {},
        ticker_order=ctx.priority_tickers,
    )

    return DigestResult(
        narrative=state.digest_narrative,
        what_to_watch=state.what_to_watch,
        digest_date=digest_date,
        span_type=span_type,
        span_label=span_label,
        priority_tickers=ctx.priority_tickers,
        important_events=important_events,
        focus_snapshot=focus_snapshot,
        references=state.references,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        models_used=models_used,
    )

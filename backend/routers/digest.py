"""User Daily Brief API: generate and retrieve tailored daily market briefs for the current user."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import Execution, Report
from services import token_service
from services.report_service import save_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["digest"])


class DigestResponse(BaseModel):
    narrative: str
    what_to_watch: str
    digest_date: str
    priority_tickers: list[str]
    references: Optional[list[dict]] = None
    user_note: Optional[str] = None
    narrative_style: Optional[str] = None
    user_focus_tickers: Optional[list[str]] = None
    raw_metadata: Optional[dict] = None


class DigestDatesResponse(BaseModel):
    dates: list[str]
    count_by_date: dict[str, int]  # date (YYYY-MM-DD) -> number of briefs that day


class DigestBriefItem(BaseModel):
    execution_id: int
    created_at: str  # ISO format
    narrative: str
    what_to_watch: str
    digest_date: str
    priority_tickers: list[str]
    user_note: Optional[str] = None
    narrative_style: Optional[str] = None
    user_focus_tickers: Optional[list[str]] = None
    raw_metadata: Optional[dict] = None


class DigestListForDateResponse(BaseModel):
    date: str
    briefs: list[DigestBriefItem]


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="Date for the digest (YYYY-MM-DD). Default: today."),
    max_priority_tickers: int = Query(5, ge=1, le=20, description="Max tickers to analyze in depth"),
    user_note: Optional[str] = Query(
        None,
        max_length=2000,
        description="Optional free-form note from the user to be considered by the digest writer.",
    ),
    narrative_style: Optional[str] = Query(
        None,
        max_length=64,
        description=(
            "Optional style preference for the brief narrative, e.g. "
            "'concise', 'professional', 'technical', 'story-like'."
        ),
    ),
    user_focus_tickers: Optional[list[str]] = Query(
        None,
        description=(
            "Optional explicit list of portfolio tickers the brief should focus on. "
            "If provided, this strongly guides focus selection."
        ),
    ),
):
    """
    Generate a short, tailored User Daily Brief for the current user's portfolio (and persist it).

    Uses the user's subscribed tickers, ranks them by attention (moves, news), fetches
    evidence and platform reports, then runs interpretation agents to produce a
    narrative brief and a "what to watch" section.
    """
    digest_date = date or datetime.utcnow().strftime("%Y-%m-%d")

    try:
        from ai_engine.daily_digest import run_digest
    except ImportError as e:
        logger.exception("Digest module not available: %s", e)
        raise HTTPException(status_code=503, detail="Digest service unavailable")

    try:
        result = await asyncio.to_thread(
            run_digest,
            user_id=current_user.id,
            digest_date=digest_date,
            db=db,
            config=None,
            max_priority_tickers=max_priority_tickers,
            user_note=user_note,
            narrative_style=narrative_style,
            user_focus_tickers=user_focus_tickers,
        )
    except Exception as e:
        logger.exception("Digest generation failed for user_id=%s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {e}")

    # Persist the digest as a generic Execution + Report (best-effort; failures don't break the API).
    try:
        subject_id = f"{current_user.id}:{digest_date}"
        execution_id = token_service.record_execution(
            creator_id=current_user.id,
            execution_type="daily_digest",
            subject_type="user_date",
            subject_id=subject_id,
            db=db,
        )
        metadata = {
            "digest_date": result.digest_date,
            "priority_tickers": result.priority_tickers,
            "what_to_watch": result.what_to_watch,
        }
        if user_note:
            metadata["user_note"] = user_note
        if narrative_style:
            metadata["narrative_style"] = narrative_style
        if user_focus_tickers:
            metadata["user_focus_tickers"] = user_focus_tickers
        # Attach LLM usage metadata when available
        if result.input_tokens is not None:
            metadata["input_tokens"] = result.input_tokens
        if result.output_tokens is not None:
            metadata["output_tokens"] = result.output_tokens
        if result.total_tokens is not None:
            metadata["total_tokens"] = result.total_tokens
        if result.cost_usd is not None:
            metadata["cost_usd"] = result.cost_usd
        if result.models_used is not None:
            metadata["models_used"] = result.models_used
        save_report(
            execution_id,
            "daily_digest",
            content=result.narrative,
            metadata=metadata,
        )
        logger.info(
            "Persisted daily digest execution_id=%s user_id=%s date=%s",
            execution_id,
            current_user.id,
            digest_date,
        )
    except Exception as e:
        logger.exception(
            "Failed to persist daily digest for user_id=%s date=%s: %s",
            current_user.id,
            digest_date,
            e,
        )

    return DigestResponse(
        narrative=result.narrative,
        what_to_watch=result.what_to_watch,
        digest_date=result.digest_date,
        priority_tickers=result.priority_tickers,
        references=[r.model_dump() for r in (result.references or [])] if hasattr(result, "references") else None,
        user_note=user_note,
        narrative_style=narrative_style,
        user_focus_tickers=user_focus_tickers,
        raw_metadata=metadata,
    )


@router.get("/digest/history/dates", response_model=DigestDatesResponse)
def get_digest_dates(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=1, le=365, description="Look back this many days from today for digest history"),
):
    """
    Return dates (YYYY-MM-DD) that have at least one digest, and how many briefs per date.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    rows = (
        db.query(Execution.subject_id)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == current_user.id,
            Execution.created_at >= since,
        )
        .all()
    )
    count_by_date: dict[str, int] = {}
    for (subject_id,) in rows:
        if not subject_id:
            continue
        parts = str(subject_id).split(":", 1)
        if len(parts) != 2:
            continue
        _uid, date_str = parts
        if date_str:
            count_by_date[date_str] = count_by_date.get(date_str, 0) + 1
    dates = sorted(count_by_date.keys())
    return DigestDatesResponse(dates=dates, count_by_date=count_by_date)


def _report_to_brief_item(ex: Execution, report: Report, date: str) -> DigestBriefItem:
    meta: dict = {}
    if report.metadata_json:
        try:
            meta = json.loads(report.metadata_json) or {}
        except Exception:
            meta = {}
    narrative = report.content or ""
    what_to_watch = str(meta.get("what_to_watch") or "")
    digest_date = str(meta.get("digest_date") or date)
    priority_tickers = meta.get("priority_tickers") or []
    if not isinstance(priority_tickers, list):
        priority_tickers = []
    user_note = meta.get("user_note")
    narrative_style = meta.get("narrative_style")
    user_focus_tickers = meta.get("user_focus_tickers") or None
    if user_focus_tickers is not None and not isinstance(user_focus_tickers, list):
        user_focus_tickers = None
    created_at = ex.created_at.isoformat() if ex.created_at else ""
    return DigestBriefItem(
        execution_id=ex.id,
        created_at=created_at,
        narrative=narrative,
        what_to_watch=what_to_watch,
        digest_date=digest_date,
        priority_tickers=[str(t) for t in priority_tickers],
        user_note=str(user_note) if user_note is not None else None,
        narrative_style=str(narrative_style) if narrative_style is not None else None,
        user_focus_tickers=[str(t) for t in (user_focus_tickers or [])] or None,
        raw_metadata=meta or None,
    )


@router.get("/digest/history/{date}", response_model=DigestListForDateResponse)
def get_digests_for_date(
    date: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all stored daily briefs for the given date (YYYY-MM-DD) for the current user,
    newest first. Does not re-run the digest workflow.
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    subject_id = f"{current_user.id}:{date}"
    executions = (
        db.query(Execution)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.subject_id == subject_id,
            Execution.creator_id == current_user.id,
        )
        .order_by(Execution.created_at.desc())
        .all()
    )
    if not executions:
        return DigestListForDateResponse(date=date, briefs=[])

    briefs: list[DigestBriefItem] = []
    for ex in executions:
        report = (
            db.query(Report)
            .filter(
                Report.execution_id == ex.id,
                Report.report_type == "daily_digest",
            )
            .first()
        )
        if report:
            briefs.append(_report_to_brief_item(ex, report, date))

    return DigestListForDateResponse(date=date, briefs=briefs)

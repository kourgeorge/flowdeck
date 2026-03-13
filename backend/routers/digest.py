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


class DigestDatesResponse(BaseModel):
    dates: list[str]


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="Date for the digest (YYYY-MM-DD). Default: today."),
    max_priority_tickers: int = Query(5, ge=1, le=20, description="Max tickers to analyze in depth"),
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
    )


@router.get("/digest/history/dates", response_model=DigestDatesResponse)
def get_digest_dates(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = Query(90, ge=1, le=365, description="Look back this many days from today for digest history"),
):
    """
    Return dates (YYYY-MM-DD) for which the current user has a stored daily digest in the recent window.
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
        .order_by(Execution.created_at.desc())
        .all()
    )
    dates: set[str] = set()
    for (subject_id,) in rows:
        if not subject_id:
            continue
        parts = str(subject_id).split(":", 1)
        if len(parts) != 2:
            continue
        _uid, date_str = parts
        if date_str:
            dates.add(date_str)
    return DigestDatesResponse(dates=sorted(dates))


@router.get("/digest/history/{date}", response_model=DigestResponse)
def get_digest_for_date(
    date: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a previously stored daily digest for the given date (YYYY-MM-DD) for the current user.
    Does not re-run the digest workflow.
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    subject_id = f"{current_user.id}:{date}"
    ex = (
        db.query(Execution)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.subject_id == subject_id,
            Execution.creator_id == current_user.id,
        )
        .order_by(Execution.created_at.desc())
        .first()
    )
    if not ex:
        raise HTTPException(status_code=404, detail="No digest found for this date")

    report = (
        db.query(Report)
        .filter(
            Report.execution_id == ex.id,
            Report.report_type == "daily_digest",
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No digest content found for this date")

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

    return DigestResponse(
        narrative=narrative,
        what_to_watch=what_to_watch,
        digest_date=digest_date,
        priority_tickers=[str(t) for t in priority_tickers],
    )

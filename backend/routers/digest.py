"""User Daily Brief API: generate and retrieve tailored daily market briefs for the current user."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services.digest_service import (
    run_and_store_digest,
    delete_brief as svc_delete_brief,
    get_digest_dates as svc_get_digest_dates,
    get_digests_for_date as svc_get_digests_for_date,
)
from services.report_service import save_report
from services.share_service import get_share_url
from services.email_service import send_daily_digest_email_to_user
from models.db_models import Execution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["digest"])


class DigestResponse(BaseModel):
    execution_id: Optional[int] = None
    narrative: str
    what_to_watch: str
    digest_date: str
    priority_tickers: list[str]
    span_type: str = "daily"
    span_label: str = "Daily"
    references: Optional[list[dict]] = None
    user_note: Optional[str] = None
    narrative_style: Optional[str] = None
    user_focus_tickers: Optional[list[str]] = None
    raw_metadata: Optional[dict] = None
    share_url: Optional[str] = None


class DigestDatesResponse(BaseModel):
    dates: list[str]
    count_by_date: dict[str, int]  # date (YYYY-MM-DD) -> number of briefs that day


class DigestBriefItem(BaseModel):
    execution_id: int
    created_at: str  # ISO format
    narrative: str
    what_to_watch: str
    digest_date: str
    span_type: str = "daily"
    span_label: str = "Daily"
    priority_tickers: list[str]
    user_note: Optional[str] = None
    narrative_style: Optional[str] = None
    user_focus_tickers: Optional[list[str]] = None
    references: Optional[list[dict]] = None
    raw_metadata: Optional[dict] = None
    share_url: Optional[str] = None


class DigestListForDateResponse(BaseModel):
    date: str
    briefs: list[DigestBriefItem]


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="Date for the digest (YYYY-MM-DD). Default: today. For weekly, end date."),
    span: Optional[str] = Query(
        "daily",
        description="Time span: 'daily' (single day) or 'weekly' (7 days ending on date).",
    ),
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
    narrative brief and a "what to watch" section. Use span=daily (default) or span=weekly.
    """
    digest_date = date or datetime.utcnow().strftime("%Y-%m-%d")
    span_type = span or "daily"

    try:
        result, metadata, execution_id, _slot = await run_and_store_digest(
            db,
            current_user.id,
            digest_date=digest_date,
            span_type=span_type,
            max_priority_tickers=max_priority_tickers,
            user_note=user_note,
            narrative_style=narrative_style,
            user_focus_tickers=user_focus_tickers,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=402,
            detail=str(e),
        )
    except ImportError as e:
        logger.exception("Digest module not available: %s", e)
        raise HTTPException(status_code=503, detail="Digest service unavailable")
    except Exception as e:  # pragma: no cover - bubble to client
        logger.exception("Digest generation failed for user_id=%s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {e}")

    share_url = get_share_url(execution_id) if execution_id else None
    return DigestResponse(
        narrative=result.narrative,
        what_to_watch=result.what_to_watch,
        digest_date=result.digest_date,
        priority_tickers=result.priority_tickers,
        span_type=getattr(result, "span_type", "daily"),
        span_label=getattr(result, "span_label", "Daily"),
        references=[r.model_dump() for r in (result.references or [])] if hasattr(result, "references") else None,
        user_note=user_note,
        narrative_style=narrative_style,
        user_focus_tickers=user_focus_tickers,
        raw_metadata=metadata,
        share_url=share_url,
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
    dates, count_by_date = svc_get_digest_dates(db, current_user.id, days)
    return DigestDatesResponse(dates=dates, count_by_date=count_by_date)


def _validate_slot(slot: str) -> None:
    """Slot is YYYY-MM-DD (daily) or w:YYYY-MM-DD (weekly)."""
    if slot.startswith("w:"):
        datetime.strptime(slot[2:], "%Y-%m-%d")
    else:
        datetime.strptime(slot, "%Y-%m-%d")


def _brief_item_to_response(b) -> DigestBriefItem:
    """Map service DigestBriefItem to Pydantic DigestBriefItem."""
    share_url = get_share_url(b.execution_id)
    return DigestBriefItem(
        execution_id=b.execution_id,
        created_at=b.created_at,
        narrative=b.narrative,
        what_to_watch=b.what_to_watch,
        digest_date=b.digest_date,
        span_type=b.span_type,
        span_label=b.span_label,
        priority_tickers=b.priority_tickers,
        user_note=b.user_note,
        narrative_style=b.narrative_style,
        user_focus_tickers=b.user_focus_tickers,
        references=b.references,
        raw_metadata=b.raw_metadata,
        share_url=share_url,
    )


@router.get("/digest/history/{date}", response_model=DigestListForDateResponse)
def get_digests_for_date(
    date: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all stored briefs for the given slot for the current user, newest first.
    Slot: YYYY-MM-DD (daily) or w:YYYY-MM-DD (weekly ending that date). Does not re-run the digest workflow.
    """
    try:
        _validate_slot(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid slot format, expected YYYY-MM-DD or w:YYYY-MM-DD")

    brief_objs = svc_get_digests_for_date(db, current_user.id, date)
    briefs = [_brief_item_to_response(b) for b in brief_objs]
    return DigestListForDateResponse(date=date, briefs=briefs)


@router.delete("/digest/briefs/{execution_id}", status_code=204)
def delete_brief(
    execution_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a User Daily Brief by execution_id. Only the creator can delete. Returns 204 on success, 404 if not found."""
    if not svc_delete_brief(db, current_user.id, execution_id):
        raise HTTPException(status_code=404, detail="Brief not found or you do not have permission to delete it")


@router.post("/digest/briefs/{execution_id}/send-email", status_code=204)
def send_brief_email(
    execution_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Email a User Daily Brief to the current user's email address.
    Only the brief owner can trigger this.
    """
    ex = (
        db.query(Execution)
        .filter(
            Execution.id == execution_id,
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == current_user.id,
        )
        .first()
    )
    if not ex:
        raise HTTPException(status_code=404, detail="Brief not found or you do not have permission to email it")

    ok = send_daily_digest_email_to_user(execution_id, current_user.email or "")
    if not ok:
        raise HTTPException(status_code=503, detail="Digest email service unavailable")

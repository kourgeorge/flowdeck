"""User Daily Brief API: generate a tailored daily market brief for the current user."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["digest"])


class DigestResponse(BaseModel):
    narrative: str
    what_to_watch: str
    digest_date: str
    priority_tickers: list[str]


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    date: Optional[str] = Query(None, description="Date for the digest (YYYY-MM-DD). Default: today."),
    max_priority_tickers: int = Query(5, ge=1, le=20, description="Max tickers to analyze in depth"),
):
    """
    Generate a short, tailored User Daily Brief for the current user's portfolio.

    Uses the user's subscribed tickers, ranks them by attention (moves, news), fetches
    evidence and platform reports, then runs interpretation agents to produce a
    narrative brief and a "what to watch" section.
    """
    from datetime import datetime
    digest_date = date or datetime.utcnow().strftime("%Y-%m-%d")

    try:
        from ai_engine.daily_digest import run_digest
    except ImportError as e:
        logger.exception("Digest module not available: %s", e)
        from fastapi import HTTPException
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
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Digest generation failed: {e}")

    return DigestResponse(
        narrative=result.narrative,
        what_to_watch=result.what_to_watch,
        digest_date=result.digest_date,
        priority_tickers=result.priority_tickers,
    )

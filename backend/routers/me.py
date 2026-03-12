"""Current user profile and stats (/api/me)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_admin_user, hash_password, verify_password
from database import get_db
from models.db_models import User, AnalysisRun, ReportView, Subscription
from services import token_service

router = APIRouter(prefix="/api", tags=["me"])


class UserStatsResponse(BaseModel):
    analyses_created: int
    tokens_spent_on_analyses: int
    tokens_earned_from_views: int
    reports_viewed: int
    unique_tickers_analyzed: int
    subscriptions_count: int
    member_since: str


class MeResponse(BaseModel):
    user_id: int
    email: str
    name: Optional[str] = None
    token_balance: int
    is_admin: bool = False
    has_password: bool = True


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class TopUpRequest(BaseModel):
    amount: int


@router.get("/me", response_model=MeResponse)
async def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return current user profile and token balance."""
    balance = token_service.get_balance(current_user.id, db)
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=getattr(current_user, "name", None) or None,
        token_balance=balance,
        is_admin=getattr(current_user, "is_admin", False),
        has_password=current_user.hashed_password is not None,
    )


@router.patch("/me", response_model=MeResponse)
async def update_me(
    body: UpdateProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update name and/or password. If new_password is provided, current_password is required."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(body.new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        user.hashed_password = hash_password(body.new_password)
    if body.name is not None:
        user.name = (body.name or "").strip() or None
    db.commit()
    db.refresh(user)
    balance = token_service.get_balance(user.id, db)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=getattr(user, "name", None) or None,
        token_balance=balance,
        is_admin=getattr(user, "is_admin", False),
    )


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_me_stats(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return usage statistics for the current user."""
    analyses_created = (
        db.query(sqla_func.count(AnalysisRun.id))
        .filter(AnalysisRun.creator_id == current_user.id)
        .scalar() or 0
    )
    tokens_earned = (
        db.query(sqla_func.coalesce(sqla_func.sum(AnalysisRun.earned_tokens), 0))
        .filter(AnalysisRun.creator_id == current_user.id)
        .scalar() or 0
    )
    reports_viewed = (
        db.query(sqla_func.count(ReportView.id))
        .filter(ReportView.viewer_id == current_user.id)
        .scalar() or 0
    )
    unique_tickers = (
        db.query(sqla_func.count(sqla_func.distinct(AnalysisRun.ticker)))
        .filter(AnalysisRun.creator_id == current_user.id)
        .scalar() or 0
    )
    subscriptions_count = (
        db.query(sqla_func.count(Subscription.id))
        .filter(Subscription.user_id == current_user.id)
        .scalar() or 0
    )
    member_since = getattr(current_user, "created_at", None)
    member_since_str = member_since.strftime("%Y-%m-%d") if member_since else ""

    return UserStatsResponse(
        analyses_created=int(analyses_created),
        tokens_spent_on_analyses=int(analyses_created) * 200,
        tokens_earned_from_views=int(tokens_earned),
        reports_viewed=int(reports_viewed),
        unique_tickers_analyzed=int(unique_tickers),
        subscriptions_count=int(subscriptions_count),
        member_since=member_since_str,
    )


@router.post("/tokens/top-up")
async def top_up_tokens(
    body: TopUpRequest,
    current_user=Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Add tokens to a user's balance (admin only). Use positive amount for credit."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    token_service.top_up(current_user.id, body.amount, db)
    return {"token_balance": token_service.get_balance(current_user.id, db)}

"""Current user profile and stats (/api/me)."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user, get_current_admin_user
from database import get_db
from services import token_service
from services import me_service
from services import user_profile_service

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
    has_completed_investor_profile: bool = False


class InvestorProfileResponse(BaseModel):
    user_id: int
    date_of_birth: Optional[date] = None
    persona_type: Optional[str] = None
    experience_level: Optional[str] = None
    risk_tolerance: Optional[str] = None
    time_horizon: Optional[str] = None
    primary_goal: Optional[str] = None
    goals: list[str] = []
    constraints: list[str] = []
    preferred_style: Optional[str] = None
    ai_memory_text: Optional[str] = None
    has_completed_investor_profile: bool = False
    onboarding_completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class UpdateInvestorProfileRequest(BaseModel):
    date_of_birth: Optional[date] = None
    persona_type: Optional[str] = None
    experience_level: Optional[str] = None
    risk_tolerance: Optional[str] = None
    time_horizon: Optional[str] = None
    primary_goal: Optional[str] = None
    goals: Optional[list[str]] = None
    constraints: Optional[list[str]] = None
    preferred_style: Optional[str] = None
    ai_memory_text: Optional[str] = None


class TopUpRequest(BaseModel):
    amount: int


@router.get("/me", response_model=MeResponse)
async def get_me(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return current user profile and token balance."""
    balance = token_service.get_balance(current_user.id, db)
    profile = me_service.get_profile(current_user, balance)
    return MeResponse(**profile)


@router.patch("/me", response_model=MeResponse)
async def update_me(
    body: UpdateProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update name and/or password. If new_password is provided, current_password is required."""
    try:
        user = me_service.update_profile(
            db,
            current_user.id,
            name=body.name,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "User not found":
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    balance = token_service.get_balance(user.id, db)
    profile = me_service.get_profile(user, balance)
    return MeResponse(**profile)


@router.get("/me/investor-profile", response_model=InvestorProfileResponse)
async def get_investor_profile(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's structured investor profile and editable AI memory."""
    profile = user_profile_service.get_profile(db, current_user.id)
    db.commit()
    return InvestorProfileResponse(**user_profile_service.serialize_profile(profile))


@router.patch("/me/investor-profile", response_model=InvestorProfileResponse)
async def update_investor_profile(
    body: UpdateInvestorProfileRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's structured investor profile and editable AI memory."""
    try:
        profile = user_profile_service.update_profile(
            db,
            current_user.id,
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return InvestorProfileResponse(**user_profile_service.serialize_profile(profile))


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_me_stats(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return usage statistics for the current user."""
    stats = me_service.get_user_stats(db, current_user.id)
    return UserStatsResponse(**stats)


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

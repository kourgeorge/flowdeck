"""Admin-only API: stats, users, reports, analyses, subscriptions."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from database import get_db
from models.db_models import User, Report, AnalysisRun, ReportView, Subscription
from services import token_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Response schemas ---

class AdminStatsResponse(BaseModel):
    total_users: int
    total_reports: int
    total_analysis_runs: int
    total_report_views: int
    total_subscriptions: int
    analyses_last_24h: int
    analyses_last_7d: int
    reports_last_24h: int
    reports_last_7d: int


class AdminUserItem(BaseModel):
    id: int
    email: str
    name: Optional[str]
    token_balance: int
    created_at: datetime
    subscription_count: int


class AdminUsersResponse(BaseModel):
    users: list[AdminUserItem]
    total: int


class AdminReportItem(BaseModel):
    id: int
    ticker: str
    run_id: str
    report_type: str
    created_at: datetime


class AdminReportsResponse(BaseModel):
    reports: list[AdminReportItem]
    total: int


class AdminAnalysisItem(BaseModel):
    id: int
    ticker: str
    run_id: str
    creator_id: int
    creator_email: str
    earned_tokens: int
    created_at: datetime


class AdminAnalysesResponse(BaseModel):
    analyses: list[AdminAnalysisItem]
    total: int


class AdminSubscriptionItem(BaseModel):
    id: int
    user_id: int
    user_email: str
    ticker: str
    created_at: datetime


class AdminSubscriptionsResponse(BaseModel):
    subscriptions: list[AdminSubscriptionItem]
    total: int


class AdminAddTokensBody(BaseModel):
    amount: int


class AdminAddTokensResponse(BaseModel):
    token_balance: int


# --- Endpoints ---

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Dashboard summary: counts and recent activity."""
    now = datetime.now(timezone.utc)
    t24 = now - timedelta(hours=24)
    t7d = now - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_reports = db.query(func.count(Report.id)).scalar() or 0
    total_analysis_runs = db.query(func.count(AnalysisRun.id)).scalar() or 0
    total_report_views = db.query(func.count(ReportView.id)).scalar() or 0
    total_subscriptions = db.query(func.count(Subscription.id)).scalar() or 0

    analyses_last_24h = (
        db.query(func.count(AnalysisRun.id)).filter(AnalysisRun.created_at >= t24).scalar() or 0
    )
    analyses_last_7d = (
        db.query(func.count(AnalysisRun.id)).filter(AnalysisRun.created_at >= t7d).scalar() or 0
    )
    reports_last_24h = (
        db.query(func.count(Report.id)).filter(Report.created_at >= t24).scalar() or 0
    )
    reports_last_7d = (
        db.query(func.count(Report.id)).filter(Report.created_at >= t7d).scalar() or 0
    )

    return AdminStatsResponse(
        total_users=total_users,
        total_reports=total_reports,
        total_analysis_runs=total_analysis_runs,
        total_report_views=total_report_views,
        total_subscriptions=total_subscriptions,
        analyses_last_24h=analyses_last_24h,
        analyses_last_7d=analyses_last_7d,
        reports_last_24h=reports_last_24h,
        reports_last_7d=reports_last_7d,
    )


@router.get("/users", response_model=AdminUsersResponse)
def get_admin_users(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List users with subscription count. Paginated."""
    total = db.query(func.count(User.id)).scalar() or 0
    rows = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # Subscription count per user
    user_ids = [u.id for u in rows]
    sub_counts = (
        db.query(Subscription.user_id, func.count(Subscription.id))
        .filter(Subscription.user_id.in_(user_ids))
        .group_by(Subscription.user_id)
    )
    count_by_user = {uid: c for uid, c in sub_counts}

    items = [
        AdminUserItem(
            id=u.id,
            email=u.email,
            name=u.name,
            token_balance=u.token_balance,
            created_at=u.created_at,
            subscription_count=count_by_user.get(u.id, 0),
        )
        for u in rows
    ]
    return AdminUsersResponse(users=items, total=total)


@router.post("/users/{user_id}/tokens", response_model=AdminAddTokensResponse)
def admin_add_tokens_to_user(
    user_id: int,
    body: AdminAddTokensBody,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Add tokens to a user's balance. Admin only. Use positive amount."""
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    token_service.top_up(user_id, body.amount, db)
    return AdminAddTokensResponse(token_balance=token_service.get_balance(user_id, db))


@router.get("/reports", response_model=AdminReportsResponse)
def get_admin_reports(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Latest reports. Ordered by created_at desc."""
    total = db.query(func.count(Report.id)).scalar() or 0
    rows = (
        db.query(Report)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    items = [
        AdminReportItem(
            id=r.id,
            ticker=r.ticker,
            run_id=r.run_id,
            report_type=r.report_type,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return AdminReportsResponse(reports=items, total=total)


@router.get("/analyses", response_model=AdminAnalysesResponse)
def get_admin_analyses(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent analysis runs with creator email."""
    total = db.query(func.count(AnalysisRun.id)).scalar() or 0
    rows = (
        db.query(AnalysisRun, User.email)
        .join(User, User.id == AnalysisRun.creator_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(limit)
        .all()
    )
    items = [
        AdminAnalysisItem(
            id=ar.id,
            ticker=ar.ticker,
            run_id=ar.run_id,
            creator_id=ar.creator_id,
            creator_email=email or "",
            earned_tokens=ar.earned_tokens,
            created_at=ar.created_at,
        )
        for ar, email in rows
    ]
    return AdminAnalysesResponse(analyses=items, total=total)


@router.get("/subscriptions", response_model=AdminSubscriptionsResponse)
def get_admin_subscriptions(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List subscriptions with user email. Paginated."""
    total = db.query(func.count(Subscription.id)).scalar() or 0
    rows = (
        db.query(Subscription, User.email)
        .join(User, User.id == Subscription.user_id)
        .order_by(Subscription.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        AdminSubscriptionItem(
            id=s.id,
            user_id=s.user_id,
            user_email=email or "",
            ticker=s.ticker,
            created_at=s.created_at,
        )
        for s, email in rows
    ]
    return AdminSubscriptionsResponse(subscriptions=items, total=total)

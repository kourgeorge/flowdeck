"""Admin-only API: stats, users, reports, analyses, subscriptions."""

import json
from datetime import datetime, timedelta, timezone, date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from database import get_db
import app_services
from models.db_models import User
from services import admin_service, token_service
from services.data_cache import delete_analysis_status, list_running_analyses, set_stop_requested

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _normalize_requested_tickers(
    tickers: Optional[list[str]],
    allowed_tickers: list[str],
) -> tuple[list[str], list[str]]:
    allowed_set = set(allowed_tickers)
    if not tickers:
        return (allowed_tickers, [])

    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        if ticker not in allowed_set:
            invalid.append(ticker)
            continue
        valid.append(ticker)

    return (valid, invalid)


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
    analysis_run_id: int
    report_type: str
    created_at: datetime
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class AdminReportsResponse(BaseModel):
    reports: list[AdminReportItem]
    total: int


class AdminAnalysisItem(BaseModel):
    id: int
    ticker: str
    creator_id: int
    creator_email: str
    earned_tokens: int
    created_at: datetime
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class AdminAnalysesResponse(BaseModel):
    analyses: list[AdminAnalysisItem]
    total: int


class AdminSubscriptionItem(BaseModel):
    id: int
    user_id: int
    user_email: str
    ticker: str
    email_updates: bool
    created_at: datetime


class AdminSubscriptionsResponse(BaseModel):
    subscriptions: list[AdminSubscriptionItem]
    total: int


class AdminReportViewRunItem(BaseModel):
    ticker: str
    analysis_run_id: int
    unique_views: int
    last_viewed_at: datetime


class AdminReportViewRunsResponse(BaseModel):
    runs: list[AdminReportViewRunItem]
    total_runs_with_views: int


class AdminReportViewItem(BaseModel):
    id: int
    ticker: str
    analysis_run_id: int
    viewer_id: int
    viewer_email: str
    viewer_name: Optional[str]
    viewed_at: datetime


class AdminReportViewsResponse(BaseModel):
    views: list[AdminReportViewItem]
    total: int


class AdminAddTokensBody(BaseModel):
    amount: int


class AdminAddTokensResponse(BaseModel):
    token_balance: int


class MissionControlTickerItem(BaseModel):
    ticker: str
    name: Optional[str]
    quote_type: Optional[str]
    market_cap: Optional[float]
    last_completed_at: Optional[datetime]
    sector: Optional[str]
    industry: Optional[str]
    is_running: bool
    running_analysis_id: Optional[int]  # AnalysisRun.id when running


class MissionControlResponse(BaseModel):
    items: list[MissionControlTickerItem]


class MissionControlRunBody(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    force: bool = False


class MissionControlRunItem(BaseModel):
    ticker: str
    analysis_run_id: int  # AnalysisRun.id


class MissionControlRunErrorItem(BaseModel):
    ticker: str
    error: str


class MissionControlRunResponse(BaseModel):
    requested: list[str]
    triggered: list[MissionControlRunItem]
    already_running: list[MissionControlRunItem]
    skipped_existing: list[str]
    invalid_tickers: list[str]
    failed: list[MissionControlRunErrorItem]


class RunningAnalysisItem(BaseModel):
    """One running analysis from the cache (for admin list + stop)."""
    analysis_run_id: int
    ticker: str
    date: Optional[str] = None
    status: str
    agent_statuses: dict[str, str] = Field(default_factory=dict)
    current_agent: Optional[str] = None
    updated_at: Optional[str] = None


# --- Endpoints ---

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Dashboard summary: counts and recent activity."""
    stats = admin_service.get_stats(db)
    return AdminStatsResponse(**stats)


@router.get("/running-analyses", response_model=list[RunningAnalysisItem])
def get_running_analyses_list(
    _user: User = Depends(get_current_admin_user),
):
    """List all running analyses (from cache). For admin UI."""
    items = list_running_analyses("ticker")
    return [
        RunningAnalysisItem(
            analysis_run_id=it.get("analysis_run_id", 0),
            ticker=str(it.get("ticker") or ""),
            date=it.get("date"),
            status=str(it.get("status") or "running"),
            agent_statuses=it.get("agent_statuses") or {},
            current_agent=it.get("current_agent"),
            updated_at=it.get("updated_at"),
        )
        for it in items
    ]


@router.post("/running-analyses/{run_id}/stop")
def stop_running_analysis(
    run_id: int,
    _user: User = Depends(get_current_admin_user),
):
    """Signal the analysis to stop and remove it from the running list (cache)."""
    set_stop_requested(run_id)
    delete_analysis_status("ticker", run_id)
    return {"ok": True, "run_id": run_id}


@router.get("/users", response_model=AdminUsersResponse)
def get_admin_users(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List users with subscription count. Paginated."""
    items, total = admin_service.list_users(db, limit, offset)
    return AdminUsersResponse(
        users=[AdminUserItem(**u) for u in items],
        total=total,
    )


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
    if not admin_service.get_user(db, user_id):
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
    items, total = admin_service.list_reports(db, limit)
    return AdminReportsResponse(
        reports=[AdminReportItem(**it) for it in items],
        total=total,
    )


@router.get("/analyses", response_model=AdminAnalysesResponse)
def get_admin_analyses(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent analysis runs with creator email and sum of report tokens/cost."""
    items, total = admin_service.list_analyses(db, limit)
    return AdminAnalysesResponse(
        analyses=[AdminAnalysisItem(**it) for it in items],
        total=total,
    )


@router.get("/subscriptions", response_model=AdminSubscriptionsResponse)
def get_admin_subscriptions(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List subscriptions with user email. Paginated."""
    items, total = admin_service.list_subscriptions(db, limit, offset)
    return AdminSubscriptionsResponse(
        subscriptions=[AdminSubscriptionItem(**it) for it in items],
        total=total,
    )


class ViewsDailyCount(BaseModel):
    date: str
    count: int


@router.get("/views/run", response_model=AdminReportViewsResponse)
def get_views_for_run(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    analysis_run_id: int = Query(..., ge=1),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Return individual views for one analysis run with viewer identity (admin only)."""
    items, total = admin_service.get_views_for_run(db, analysis_run_id, limit, offset)
    return AdminReportViewsResponse(
        views=[AdminReportViewItem(**it) for it in items],
        total=total,
    )


@router.get("/views", response_model=AdminReportViewsResponse)
def get_views(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return individual report views with viewer identity (admin only)."""
    items, total = admin_service.get_views(db, limit, offset)
    return AdminReportViewsResponse(
        views=[AdminReportViewItem(**it) for it in items],
        total=total,
    )


@router.get("/views/runs", response_model=AdminReportViewRunsResponse)
def get_view_runs(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    """Return report runs with unique view counts, ordered for hierarchy browsing."""
    runs, total_runs_with_views = admin_service.get_view_runs(db, limit)
    return AdminReportViewRunsResponse(
        runs=[AdminReportViewRunItem(**r) for r in runs],
        total_runs_with_views=total_runs_with_views,
    )


class ViewsDailyResponse(BaseModel):
    data: list[ViewsDailyCount]


@router.get("/views/daily", response_model=ViewsDailyResponse)
def get_views_daily(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=90),
):
    """Return count of report views per day for the last N days."""
    result = admin_service.get_views_daily(db, days)
    return ViewsDailyResponse(
        data=[ViewsDailyCount(date=it["date"], count=it["count"]) for it in result]
    )


class AnalysisDailyCount(BaseModel):
    date: str  # ISO date string YYYY-MM-DD
    count: int


class AnalysesDailyResponse(BaseModel):
    data: list[AnalysisDailyCount]


@router.get("/analyses/daily", response_model=AnalysesDailyResponse)
def get_analyses_daily(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=90),
):
    """Return count of analysis runs per day for the last N days."""
    result = admin_service.get_analyses_daily(db, days)
    return AnalysesDailyResponse(
        data=[AnalysisDailyCount(date=it["date"], count=it["count"]) for it in result]
    )


@router.get("/mission-control", response_model=MissionControlResponse)
def get_mission_control(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    items_data = admin_service.get_mission_control_items(db)
    return MissionControlResponse(
        items=[MissionControlTickerItem(**it) for it in items_data]
    )


@router.post("/mission-control/run", response_model=MissionControlRunResponse)
def run_mission_control(
    body: MissionControlRunBody,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mission_entries = admin_service.load_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    requested, invalid_tickers = _normalize_requested_tickers(body.tickers, mission_tickers)
    running_by_ticker = admin_service.get_running_statuses_by_ticker(mission_tickers)
    has_report_today = admin_service.get_tickers_with_report_on_date(db, date_str)

    triggered: list[MissionControlRunItem] = []
    already_running: list[MissionControlRunItem] = []
    skipped_existing: list[str] = []
    failed: list[MissionControlRunErrorItem] = []

    for ticker in requested:
        running = running_by_ticker.get(ticker)
        if running is not None and str(running.get("date") or "") == date_str:
            run_id = running.get("analysis_run_id")
            if run_id is not None:
                already_running.append(MissionControlRunItem(ticker=ticker, analysis_run_id=run_id))
                continue

        if not body.force and ticker in has_report_today:
            skipped_existing.append(ticker)
            continue

        try:
            analysis_run_id = token_service.record_analysis_run(_user.id, ticker, db)
            returned_run_id, existing = app_services.get_analysis_service().start_analysis(
                ticker=ticker,
                analysis_date=date_str,
                analysts=["market", "social", "news", "fundamentals", "technical", "sec"],
                research_depth=5,
                llm_provider="azure",
                progress_callback=None,
                analysis_run_id=analysis_run_id,
            )
            if existing:
                # Race: another run started; remove the AnalysisRun we just created so it is not counted
                token_service.delete_execution(analysis_run_id, db)
                already_running.append(MissionControlRunItem(ticker=ticker, analysis_run_id=returned_run_id))
            else:
                triggered.append(MissionControlRunItem(ticker=ticker, analysis_run_id=returned_run_id))
        except Exception as e:
            failed.append(MissionControlRunErrorItem(ticker=ticker, error=str(e)))

    return MissionControlRunResponse(
        requested=requested,
        triggered=triggered,
        already_running=already_running,
        skipped_existing=skipped_existing,
        invalid_tickers=invalid_tickers,
        failed=failed,
    )

"""Admin-only API: stats, users, reports, analyses, subscriptions."""

import json
import os
from datetime import datetime, timedelta, timezone, date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from database import get_db
import app_services
from models.db_models import User
from services import admin_service, analytics_service, token_service
from services.data_cache import delete_analysis_status, list_running_analyses, set_stop_requested

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Base model with timezone-aware datetime serialization
class TZAwareBaseModel(BaseModel):
    """Base model that ensures datetime fields are serialized with timezone info."""
    
    @field_serializer('*', when_used='json')
    def serialize_datetime(self, value: Any, _info) -> Any:
        """Ensure datetime values are timezone-aware when serialized to JSON."""
        if isinstance(value, datetime):
            # If datetime is naive (no timezone), assume it's UTC
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value


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

class AdminStatsResponse(TZAwareBaseModel):
    total_users: int
    total_reports: int
    total_analysis_runs: int
    total_report_views: int
    total_subscriptions: int
    analyses_last_24h: int
    analyses_last_7d: int
    reports_last_24h: int
    reports_last_7d: int


class AdminUserItem(TZAwareBaseModel):
    id: int
    email: str
    name: Optional[str]
    token_balance: int
    created_at: datetime
    subscription_count: int


class AdminUsersResponse(TZAwareBaseModel):
    users: list[AdminUserItem]
    total: int


class AdminReportItem(TZAwareBaseModel):
    id: int
    ticker: str
    analysis_run_id: int
    report_type: str
    created_at: datetime
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class AdminReportsResponse(TZAwareBaseModel):
    reports: list[AdminReportItem]
    total: int


class AdminReportDetailResponse(TZAwareBaseModel):
    id: int
    ticker: str
    analysis_run_id: int
    report_type: str
    created_at: datetime
    content: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    metadata_raw: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class AdminAnalysisItem(TZAwareBaseModel):
    id: int
    ticker: str
    creator_id: int
    creator_email: str
    earned_tokens: int
    created_at: datetime
    status: str = "running"
    error_message: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None


class AdminAnalysesResponse(TZAwareBaseModel):
    analyses: list[AdminAnalysisItem]
    total: int


class AdminAccuracySummary(TZAwareBaseModel):
    total_rows: int
    scored_rows: int
    correct_count: int
    incorrect_count: int
    hold_count: int
    unavailable_count: int
    buy_count: int
    sell_count: int
    accuracy_percent: Optional[float] = None


class AdminAccuracyRow(TZAwareBaseModel):
    analysis_run_id: int
    ticker: str
    created_at: datetime
    recommendation: Optional[str] = None
    analysis_price: Optional[float] = None
    current_price: Optional[float] = None
    return_percent: Optional[float] = None
    outcome: str
    is_scored: bool = False
    quote_status: str = "unavailable"


class AdminAccuracyResponse(TZAwareBaseModel):
    period_days: int
    summary: AdminAccuracySummary
    rows: list[AdminAccuracyRow]


class AdminSubscriptionItem(TZAwareBaseModel):
    id: int
    user_id: int
    user_email: str
    ticker: str
    email_updates: bool
    created_at: datetime


class AdminSubscriptionsResponse(TZAwareBaseModel):
    subscriptions: list[AdminSubscriptionItem]
    total: int


class AdminReportViewRunItem(TZAwareBaseModel):
    ticker: str
    analysis_run_id: int
    unique_views: int
    last_viewed_at: datetime


class AdminReportViewRunsResponse(TZAwareBaseModel):
    runs: list[AdminReportViewRunItem]
    total_runs_with_views: int


class AdminReportViewItem(TZAwareBaseModel):
    id: int
    ticker: str
    analysis_run_id: int
    viewer_id: int
    viewer_email: str
    viewer_name: Optional[str]
    viewed_at: datetime


class AdminReportViewsResponse(TZAwareBaseModel):
    views: list[AdminReportViewItem]
    total: int


class AdminAddTokensBody(BaseModel):
    amount: int


class AdminAddTokensResponse(BaseModel):
    token_balance: int


class MissionControlTickerItem(TZAwareBaseModel):
    ticker: str
    name: Optional[str]
    quote_type: Optional[str]
    market_cap: Optional[float]
    last_completed_at: Optional[datetime]
    report_count: Optional[int]  # Number of reports in latest execution
    sector: Optional[str]
    industry: Optional[str]
    is_running: bool
    running_analysis_id: Optional[int]  # AnalysisRun.id when running
    subscription_count: int = 0  # Number of users subscribed to this ticker
    priority_score: float = 0.0  # Calculated priority for rerunning analysis
    last_status: Optional[str] = None  # Status of last execution: running | completed | failed


class MissionControlResponse(TZAwareBaseModel):
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
    created_at: Optional[str] = None
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
            created_at=it.get("created_at"),
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


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete a user account. Admin only. This action is irreversible."""
    try:
        deleted = admin_service.delete_user(db, user_id)
    except admin_service.CannotDeleteAdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "id": user_id}


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


@router.get("/reports/{report_id}", response_model=AdminReportDetailResponse)
def get_admin_report_detail(
    report_id: int,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Raw report payload for a single report row in admin."""
    item = admin_service.get_report_detail(db, report_id)
    if not item:
        raise HTTPException(status_code=404, detail="Report not found")
    return AdminReportDetailResponse(**item)


@router.get("/analyses", response_model=AdminAnalysesResponse)
def get_admin_analyses(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Recent analysis runs with creator email and sum of report tokens/cost."""
    items, total = admin_service.list_analyses(db, limit, offset)
    return AdminAnalysesResponse(
        analyses=[AdminAnalysisItem(**it) for it in items],
        total=total,
    )


@router.get("/analyses/{analysis_run_id}/download")
def download_analysis_reports_zip(
    analysis_run_id: int,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Download all reports for one analysis run as a zip archive."""
    payload = admin_service.build_analysis_reports_zip(db, analysis_run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Analysis reports not found")

    zip_bytes, filename = payload
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete("/analyses/{analysis_run_id}")
def delete_analysis_run(
    analysis_run_id: int,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Delete an AI analysis run and its reports (admin only). Cascades to reports and report_views."""
    delete_analysis_status("ticker", analysis_run_id)
    token_service.delete_execution(analysis_run_id, db)
    return {"ok": True, "id": analysis_run_id}


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


@router.get("/analysis-accuracy", response_model=AdminAccuracyResponse)
def get_analysis_accuracy(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=90),
):
    """Return recommendation accuracy for completed ticker analyses in the selected period."""
    result = admin_service.get_analysis_accuracy(db, days)
    return AdminAccuracyResponse(
        period_days=int(result.get("period_days") or days),
        summary=AdminAccuracySummary(**(result.get("summary") or {})),
        rows=[AdminAccuracyRow(**row) for row in (result.get("rows") or [])],
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
    
    # Read LLM provider from environment (same as regular analysis endpoint)
    llm_provider = os.environ.get("LLM_PROVIDER", "azure").strip().lower()

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
                analysts=["market", "social", "news", "fundamentals", "technical", "sec", "valuation"],
                research_depth=5,
                llm_provider=llm_provider,
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



# --- Analytics Endpoints ---

class AnalyticsCostBreakdownResponse(BaseModel):
    """Cost breakdown by operation type."""
    period_days: int
    total_cost_usd: float
    total_llm_tokens: int
    operations: list[dict[str, Any]]


class AnalyticsCostPerUserResponse(BaseModel):
    """Cost per user."""
    period_days: int
    users: list[dict[str, Any]]


class AnalyticsExpensiveOperationsResponse(BaseModel):
    """Most expensive operations."""
    period_days: int
    operations: list[dict[str, Any]]


class AnalyticsUsageTrendsResponse(BaseModel):
    """Usage trends over time."""
    period_days: int
    daily_data: list[dict[str, Any]]


class AnalyticsModelDistributionResponse(BaseModel):
    """Model usage distribution."""
    period_days: int
    models: list[dict[str, Any]]


class AnalyticsRecommendationsResponse(BaseModel):
    """Cost optimization recommendations."""
    period_days: int
    recommendations: list[dict[str, Any]]


@router.get("/analytics/cost-breakdown", response_model=AnalyticsCostBreakdownResponse)
def get_analytics_cost_breakdown(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get LLM cost breakdown by operation type (chat, analysis, digest)."""
    result = analytics_service.get_cost_breakdown_by_operation(db, days)
    return AnalyticsCostBreakdownResponse(**result)


@router.get("/analytics/cost-per-user", response_model=AnalyticsCostPerUserResponse)
def get_analytics_cost_per_user(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
):
    """Get cost per user over time period."""
    result = analytics_service.get_cost_per_user(db, days, limit)
    return AnalyticsCostPerUserResponse(**result)


@router.get("/analytics/expensive-operations", response_model=AnalyticsExpensiveOperationsResponse)
def get_analytics_expensive_operations(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
):
    """Identify most expensive individual operations."""
    result = analytics_service.get_most_expensive_operations(db, days, limit)
    return AnalyticsExpensiveOperationsResponse(**result)


@router.get("/analytics/usage-trends", response_model=AnalyticsUsageTrendsResponse)
def get_analytics_usage_trends(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get token usage and cost trends over time (daily aggregation)."""
    result = analytics_service.get_usage_trends(db, days)
    return AnalyticsUsageTrendsResponse(**result)


@router.get("/analytics/model-distribution", response_model=AnalyticsModelDistributionResponse)
def get_analytics_model_distribution(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Get distribution of LLM model usage."""
    result = analytics_service.get_model_usage_distribution(db, days)
    return AnalyticsModelDistributionResponse(**result)


@router.get("/analytics/recommendations", response_model=AnalyticsRecommendationsResponse)
def get_analytics_recommendations(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Generate cost optimization recommendations based on usage patterns."""
    result = analytics_service.get_cost_optimization_recommendations(db, days)
    return AnalyticsRecommendationsResponse(**result)

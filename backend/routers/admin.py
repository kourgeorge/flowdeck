"""Admin-only API: stats, users, reports, analyses, subscriptions."""

import json
from json import JSONDecodeError, load
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from config import RESULTS_DIR
from database import get_db
from models.db_models import User, Report, Execution, ReportView, Subscription
from services import token_service
from services.analysis_service import AnalysisService
from services.data_cache import delete_analysis_status, list_running_analyses, set_stop_requested

router = APIRouter(prefix="/api/admin", tags=["admin"])
# Use shared analysis service injected by main so mission control and API share in-memory + cache state
_analysis_service: Optional[AnalysisService] = None


def set_analysis_service(service: AnalysisService) -> None:
    """Set the shared analysis service (called from main.py)."""
    global _analysis_service
    _analysis_service = service


def _get_mission_analysis_service() -> AnalysisService:
    """Analysis service for mission control; use shared one from main when set."""
    if _analysis_service is not None:
        return _analysis_service
    return AnalysisService(results_dir=RESULTS_DIR)
_MAJOR_STOCKS_SECTORS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "major_stocks_sectors.json"
)


def _results_root() -> Path:
    p = Path(RESULTS_DIR)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parents[2] / p


def _load_mission_control_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = load(f)
    except (OSError, JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, item in data.items():
        ticker_raw = key
        name: Optional[str] = None
        sector: Optional[str] = None
        industry: Optional[str] = None
        quote_type: Optional[str] = None
        market_cap: Optional[float] = None

        if isinstance(item, dict):
            ticker_raw = item.get("ticker") or key
            name_raw = item.get("name")
            sector_raw = item.get("sector")
            industry_raw = item.get("industry")
            quote_type_raw = item.get("quote_type")
            market_cap_raw = item.get("market_cap")
            name = str(name_raw).strip() if name_raw is not None else None
            sector = str(sector_raw).strip() if sector_raw is not None else None
            industry = str(industry_raw).strip() if industry_raw is not None else None
            quote_type = (
                str(quote_type_raw).strip().upper() if quote_type_raw is not None else None
            )
            if market_cap_raw is not None:
                try:
                    market_cap = float(market_cap_raw)
                except (TypeError, ValueError):
                    market_cap = None

        ticker = str(ticker_raw or "").strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        entries.append(
            {
                "ticker": ticker,
                "name": name or None,
                "sector": sector or None,
                "industry": industry or None,
                "quote_type": quote_type or None,
                "market_cap": market_cap,
            }
        )

    entries.sort(key=lambda item: (0 if item.get("quote_type") == "EQUITY" else 1, item["ticker"] or ""))
    return entries


def _get_mission_control_entries() -> list[dict[str, Any]]:
    return _load_mission_control_entries(_MAJOR_STOCKS_SECTORS_PATH)


def _quote_type_sort_rank(quote_type: Optional[str]) -> int:
    return 0 if str(quote_type or "").strip().upper() == "EQUITY" else 1


def _load_running_statuses_by_ticker(tickers: list[str]) -> dict[str, dict]:
    """
    Return currently running status payload keyed by ticker (from shared cache DB).
    """
    allowed_tickers = {t.upper() for t in tickers}
    by_ticker: dict[str, dict] = {}
    for item in list_running_analyses("ticker"):
        ticker_upper = str(item.get("ticker") or "").upper()
        if not ticker_upper or ticker_upper not in allowed_tickers:
            continue
        current = by_ticker.get(ticker_upper)
        current_updated_at = str((current or {}).get("updated_at") or "")
        candidate_updated_at = str(item.get("updated_at") or "")
        if current is None or candidate_updated_at >= current_updated_at:
            by_ticker[ticker_upper] = item
    return by_ticker


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
    now = datetime.now(timezone.utc)
    t24 = now - timedelta(hours=24)
    t7d = now - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_reports = db.query(func.count(Report.id)).scalar() or 0
    total_analysis_runs = db.query(func.count(Execution.id)).scalar() or 0
    total_report_views = db.query(func.count(ReportView.id)).scalar() or 0
    total_subscriptions = db.query(func.count(Subscription.id)).scalar() or 0

    analyses_last_24h = (
        db.query(func.count(Execution.id)).filter(Execution.created_at >= t24).scalar() or 0
    )
    analyses_last_7d = (
        db.query(func.count(Execution.id)).filter(Execution.created_at >= t7d).scalar() or 0
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
    rows_with_run = (
        db.query(Report, Execution.id, Execution.subject_id)
        .outerjoin(Execution, Report.execution_id == Execution.id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for r, ex_id, subject_id in rows_with_run:
        meta = {}
        if r.metadata_json:
            try:
                meta = json.loads(r.metadata_json) or {}
            except Exception:
                pass
        items.append(
            AdminReportItem(
                id=r.id,
                ticker=subject_id or "",
                analysis_run_id=ex_id or 0,
                report_type=r.report_type,
                created_at=r.created_at,
                input_tokens=meta.get("input_tokens"),
                output_tokens=meta.get("output_tokens"),
                total_tokens=meta.get("total_tokens"),
                cost_usd=meta.get("cost_usd"),
            )
        )
    return AdminReportsResponse(reports=items, total=total)


@router.get("/analyses", response_model=AdminAnalysesResponse)
def get_admin_analyses(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent analysis runs with creator email and sum of report tokens/cost."""
    total = db.query(func.count(Execution.id)).scalar() or 0
    rows = (
        db.query(Execution, User.email)
        .join(User, User.id == Execution.creator_id)
        .order_by(Execution.created_at.desc())
        .limit(limit)
        .all()
    )
    ex_ids = [ex.id for ex, _ in rows]
    sums_by_ex: dict[int, tuple[int, int, float]] = {}
    if ex_ids:
        reports = (
            db.query(Report.execution_id, Report.metadata_json)
            .filter(Report.execution_id.in_(ex_ids))
            .all()
        )
        for ex_id, meta_json in reports:
            if ex_id is None:
                continue
            meta = {}
            if meta_json:
                try:
                    meta = json.loads(meta_json) or {}
                except Exception:
                    pass
            inp = meta.get("input_tokens")
            out = meta.get("output_tokens")
            cost = meta.get("cost_usd")
            if cost is not None:
                cost = float(cost)
            prev_inp, prev_out, prev_cost = sums_by_ex.get(ex_id, (0, 0, 0.0))
            sums_by_ex[ex_id] = (
                prev_inp + (int(inp) if inp is not None else 0),
                prev_out + (int(out) if out is not None else 0),
                prev_cost + (cost if cost is not None else 0.0),
            )
    items = []
    for ex, email in rows:
        inp, out, cost = sums_by_ex.get(ex.id, (0, 0, 0.0))
        tot = inp + out
        items.append(
            AdminAnalysisItem(
                id=ex.id,
                ticker=ex.subject_id if ex.execution_type == "ticker" else ex.subject_id or "",
                creator_id=ex.creator_id,
                creator_email=email or "",
                earned_tokens=ex.earned_tokens,
                created_at=ex.created_at,
                input_tokens=inp if inp else None,
                output_tokens=out if out else None,
                total_tokens=tot if tot else None,
                cost_usd=round(cost, 6) if cost else None,
            )
        )
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
            email_updates=getattr(s, "email_updates", True),
            created_at=s.created_at,
        )
        for s, email in rows
    ]
    return AdminSubscriptionsResponse(subscriptions=items, total=total)


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
    ex = db.query(Execution).filter(Execution.id == analysis_run_id).first()
    if not ex:
        return AdminReportViewsResponse(views=[], total=0)
    ticker_upper = (ex.subject_id or "").upper() if ex.execution_type == "ticker" else (ex.subject_id or "")
    base_query = (
        db.query(ReportView, User.email, User.name)
        .outerjoin(User, User.id == ReportView.viewer_id)
        .filter(ReportView.execution_id == ex.id)
    )
    total = base_query.count() or 0
    rows = (
        base_query
        .order_by(ReportView.viewed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        AdminReportViewItem(
            id=view.id,
            ticker=ticker_upper,
            analysis_run_id=ex.id,
            viewer_id=view.viewer_id,
            viewer_email=email or f"[deleted user id={view.viewer_id}]",
            viewer_name=name,
            viewed_at=view.viewed_at,
        )
        for view, email, name in rows
    ]
    return AdminReportViewsResponse(views=items, total=total)


@router.get("/views", response_model=AdminReportViewsResponse)
def get_views(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return individual report views with viewer identity (admin only)."""
    total = db.query(func.count(ReportView.id)).scalar() or 0
    rows = (
        db.query(ReportView, Execution.subject_id, Execution.id, User.email, User.name)
        .outerjoin(Execution, ReportView.execution_id == Execution.id)
        .outerjoin(User, User.id == ReportView.viewer_id)
        .order_by(ReportView.viewed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        AdminReportViewItem(
            id=view.id,
            ticker=(ticker or "").upper(),
            analysis_run_id=ex_id or 0,
            viewer_id=view.viewer_id,
            viewer_email=email or f"[deleted user id={view.viewer_id}]",
            viewer_name=name,
            viewed_at=view.viewed_at,
        )
        for view, ticker, ex_id, email, name in rows
    ]
    return AdminReportViewsResponse(views=items, total=total)


@router.get("/views/runs", response_model=AdminReportViewRunsResponse)
def get_view_runs(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    """Return report runs with unique view counts, ordered for hierarchy browsing."""
    rows = (
        db.query(
            Execution.subject_id,
            Execution.id,
            func.count(ReportView.id).label("unique_views"),
            func.max(ReportView.viewed_at).label("last_viewed_at"),
        )
        .join(ReportView, ReportView.execution_id == Execution.id)
        .group_by(Execution.id, Execution.subject_id)
        .order_by(
            Execution.id.desc(),
            Execution.subject_id.asc(),
            func.max(ReportView.viewed_at).desc(),
            func.count(ReportView.id).desc(),
        )
        .limit(limit)
        .all()
    )
    total_runs_with_views = (
        db.query(func.count(func.distinct(ReportView.execution_id)))
        .filter(ReportView.execution_id.isnot(None))
        .scalar()
        or 0
    )

    items = [
        AdminReportViewRunItem(
            ticker=(ticker or "").upper(),
            analysis_run_id=ex_id,
            unique_views=int(unique_views or 0),
            last_viewed_at=last_viewed_at,
        )
        for ticker, ex_id, unique_views, last_viewed_at in rows
        if last_viewed_at is not None
    ]
    return AdminReportViewRunsResponse(
        runs=items,
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
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            func.date(ReportView.viewed_at).label("day"),
            func.count(ReportView.id).label("count"),
        )
        .filter(ReportView.viewed_at >= since)
        .group_by("day")
        .order_by("day")
        .all()
    )
    today = date.today()
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    count_by_day = {r.day: r.count for r in rows}  # type: ignore
    result = []
    current = start
    while current <= today:
        date_str = str(current)
        count_val = count_by_day.get(date_str, 0)  # type: ignore[arg-type]
        result.append(ViewsDailyCount(date=date_str, count=count_val))  # type: ignore[arg-type]
        current += timedelta(days=1)
    return ViewsDailyResponse(data=result)


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
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            func.date(Execution.created_at).label("day"),
            func.count(Execution.id).label("count"),
        )
        .filter(Execution.created_at >= since)
        .group_by("day")
        .order_by("day")
        .all()
    )
    # Build a full date range with 0-fill for missing days
    today = date.today()
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    count_by_day = {r.day: r.count for r in rows}  # type: ignore
    result = []
    current = start
    while current <= today:
        date_str = str(current)
        count_val = count_by_day.get(date_str, 0)  # type: ignore[arg-type]
        result.append(AnalysisDailyCount(date=date_str, count=count_val))  # type: ignore[arg-type]
        current += timedelta(days=1)
    return AnalysesDailyResponse(data=result)


@router.get("/mission-control", response_model=MissionControlResponse)
def get_mission_control(
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    mission_entries = _get_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    ticker_set = set(mission_tickers)
    running_by_ticker = _load_running_statuses_by_ticker(mission_tickers)
    # last_completed used for sort order and display
    last_completed = {
        str(subject_id).upper(): created_at
        for subject_id, created_at in db.query(
            Execution.subject_id, func.max(Report.created_at)
        )
        .join(Report, Report.execution_id == Execution.id)
        .filter(Execution.execution_type == "ticker")
        .group_by(Execution.subject_id)
        .all()
        if subject_id and str(subject_id).upper() in ticker_set and created_at is not None
    }

    def _entry_sort_key(entry: dict[str, Any]) -> tuple[int, int, float, str]:
        ticker_upper = str(entry.get("ticker") or "").upper()
        completed_at = last_completed.get(ticker_upper)
        completed_ts = completed_at.timestamp() if completed_at is not None else 0.0
        return (
            _quote_type_sort_rank(entry.get("quote_type")),
            0 if completed_at is not None else 1,
            -completed_ts,
            ticker_upper,
        )

    items: list[MissionControlTickerItem] = []
    for entry in sorted(mission_entries, key=_entry_sort_key):
        ticker_upper = str(entry.get("ticker") or "").upper()
        if not ticker_upper:
            continue
        running = running_by_ticker.get(ticker_upper)
        items.append(
            MissionControlTickerItem(
                ticker=ticker_upper,
                name=entry.get("name"),
                quote_type=entry.get("quote_type"),
                market_cap=entry.get("market_cap"),
                last_completed_at=last_completed.get(ticker_upper),
                sector=entry.get("sector"),
                industry=entry.get("industry"),
                is_running=running is not None,
                running_analysis_id=running.get("analysis_run_id") if running else None,
            )
        )

    return MissionControlResponse(items=items)


@router.post("/mission-control/run", response_model=MissionControlRunResponse)
def run_mission_control(
    body: MissionControlRunBody,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mission_entries = _get_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    requested, invalid_tickers = _normalize_requested_tickers(body.tickers, mission_tickers)
    running_by_ticker = _load_running_statuses_by_ticker(mission_tickers)
    has_report_today = {
        str(subject_id).upper()
        for (subject_id,) in db.query(Execution.subject_id)
        .join(Report, Report.execution_id == Execution.id)
        .filter(Execution.execution_type == "ticker", func.date(Execution.created_at) == date_str)
        .distinct()
        .all()
        if subject_id
    }

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
            returned_run_id, existing = _get_mission_analysis_service().start_analysis(
                ticker=ticker,
                analysis_date=date_str,
                analysts=["market", "news", "fundamentals", "technical", "sec"],
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

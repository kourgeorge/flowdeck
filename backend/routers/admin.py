"""Admin-only API: stats, users, reports, analyses, subscriptions."""

from json import JSONDecodeError, load
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session

from auth import get_current_admin_user
from config import RESULTS_DIR
from database import get_db
from models.db_models import User, Report, AnalysisRun, ReportView, Subscription
from services import token_service
from services.analysis_service import AnalysisService

router = APIRouter(prefix="/api/admin", tags=["admin"])
_MISSION_ANALYSIS_SERVICE = AnalysisService(results_dir=RESULTS_DIR)
_MAJOR_STOCKS_SECTORS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "major_stocks_sectors.json"
)


def _normalize_analysis_date(analysis_date: Optional[str]) -> str:
    date_str = (analysis_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="analysis_date must be YYYY-MM-DD")
    return date_str


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
        sector: Optional[str] = None
        industry: Optional[str] = None
        quote_type: Optional[str] = None
        market_cap: Optional[float] = None

        if isinstance(item, dict):
            ticker_raw = item.get("ticker") or key
            sector_raw = item.get("sector")
            industry_raw = item.get("industry")
            quote_type_raw = item.get("quote_type")
            market_cap_raw = item.get("market_cap")
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
    Return currently running status payload keyed by ticker.
    Status files are removed by AnalysisService when analyses complete/error.
    """
    root = _results_root()
    if not root.exists():
        return {}

    allowed_tickers = {t.upper() for t in tickers}
    by_ticker: dict[str, dict] = {}
    for ticker_dir in root.iterdir():
        if not ticker_dir.is_dir():
            continue
        ticker_upper = ticker_dir.name.upper()
        if ticker_upper not in allowed_tickers:
            continue

        for status_file in sorted(ticker_dir.glob("*/status.json"), key=lambda p: p.parent.name, reverse=True):
            try:
                with status_file.open("r", encoding="utf-8") as f:
                    data = load(f) or {}
            except (OSError, JSONDecodeError):
                continue

            if data.get("status") != "running":
                continue
            if str(data.get("ticker") or "").upper() != ticker_upper:
                continue

            current = by_ticker.get(ticker_upper)
            current_updated_at = str((current or {}).get("updated_at") or "")
            candidate_updated_at = str(data.get("updated_at") or "")
            if current is None or candidate_updated_at >= current_updated_at:
                by_ticker[ticker_upper] = data

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
    email_updates: bool
    created_at: datetime


class AdminSubscriptionsResponse(BaseModel):
    subscriptions: list[AdminSubscriptionItem]
    total: int


class AdminAddTokensBody(BaseModel):
    amount: int


class AdminAddTokensResponse(BaseModel):
    token_balance: int


class MissionControlTickerItem(BaseModel):
    ticker: str
    quote_type: Optional[str]
    market_cap: Optional[float]
    last_completed_at: Optional[datetime]
    sector: Optional[str]
    industry: Optional[str]
    has_report_for_date: bool
    is_running: bool
    running_analysis_id: Optional[str]
    running_for_date: Optional[str]


class MissionControlResponse(BaseModel):
    date: str
    items: list[MissionControlTickerItem]


class MissionControlRunBody(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    analysis_date: Optional[str] = None
    force: bool = False


class MissionControlRunItem(BaseModel):
    ticker: str
    analysis_id: str


class MissionControlRunErrorItem(BaseModel):
    ticker: str
    error: str


class MissionControlRunResponse(BaseModel):
    date: str
    requested: list[str]
    triggered: list[MissionControlRunItem]
    already_running: list[MissionControlRunItem]
    skipped_existing: list[str]
    invalid_tickers: list[str]
    failed: list[MissionControlRunErrorItem]


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
            email_updates=getattr(s, "email_updates", True),
            created_at=s.created_at,
        )
        for s, email in rows
    ]
    return AdminSubscriptionsResponse(subscriptions=items, total=total)


class ViewsDailyCount(BaseModel):
    date: str
    count: int


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
            func.date(AnalysisRun.created_at).label("day"),
            func.count(AnalysisRun.id).label("count"),
        )
        .filter(AnalysisRun.created_at >= since)
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
    analysis_date: Optional[str] = Query(None),
):
    date_str = _normalize_analysis_date(analysis_date)
    mission_entries = _get_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    ticker_set = set(mission_tickers)
    running_by_ticker = _load_running_statuses_by_ticker(mission_tickers)

    last_completed = {
        str(ticker).upper(): created_at
        for ticker, created_at in db.query(
            Report.ticker, func.max(Report.created_at)
        ).group_by(Report.ticker).all()
        if ticker and str(ticker).upper() in ticker_set and created_at is not None
    }
    has_report_today = {
        str(ticker).upper()
        for (ticker,) in db.query(Report.ticker)
        .filter(Report.run_id.like(f"{date_str}%"))
        .distinct()
        .all()
        if ticker
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
                quote_type=entry.get("quote_type"),
                market_cap=entry.get("market_cap"),
                last_completed_at=last_completed.get(ticker_upper),
                sector=entry.get("sector"),
                industry=entry.get("industry"),
                has_report_for_date=ticker_upper in has_report_today,
                is_running=running is not None,
                running_analysis_id=(str(running.get("analysis_id")) if running else None),
                running_for_date=(str(running.get("date")) if running else None),
            )
        )

    return MissionControlResponse(date=date_str, items=items)


@router.post("/mission-control/run", response_model=MissionControlRunResponse)
def run_mission_control(
    body: MissionControlRunBody,
    _user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    date_str = _normalize_analysis_date(body.analysis_date)
    mission_entries = _get_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    requested, invalid_tickers = _normalize_requested_tickers(body.tickers, mission_tickers)
    running_by_ticker = _load_running_statuses_by_ticker(mission_tickers)
    has_report_today = {
        str(ticker).upper()
        for (ticker,) in db.query(Report.ticker)
        .filter(Report.run_id.like(f"{date_str}%"))
        .distinct()
        .all()
        if ticker
    }

    triggered: list[MissionControlRunItem] = []
    already_running: list[MissionControlRunItem] = []
    skipped_existing: list[str] = []
    failed: list[MissionControlRunErrorItem] = []

    for ticker in requested:
        running = running_by_ticker.get(ticker)
        if running is not None and str(running.get("date") or "") == date_str:
            analysis_id = str(running.get("analysis_id") or "")
            if analysis_id:
                already_running.append(MissionControlRunItem(ticker=ticker, analysis_id=analysis_id))
                continue

        if not body.force and ticker in has_report_today:
            skipped_existing.append(ticker)
            continue

        try:
            analysis_id, existing = _MISSION_ANALYSIS_SERVICE.start_analysis(
                ticker=ticker,
                analysis_date=date_str,
                analysts=["market", "news", "fundamentals", "technical", "sec"],
                research_depth=5,
                llm_provider="azure",
                progress_callback=None,
            )
            if existing:
                already_running.append(MissionControlRunItem(ticker=ticker, analysis_id=analysis_id))
            else:
                triggered.append(MissionControlRunItem(ticker=ticker, analysis_id=analysis_id))
        except Exception as e:
            failed.append(MissionControlRunErrorItem(ticker=ticker, error=str(e)))

    return MissionControlRunResponse(
        date=date_str,
        requested=requested,
        triggered=triggered,
        already_running=already_running,
        skipped_existing=skipped_existing,
        invalid_tickers=invalid_tickers,
        failed=failed,
    )

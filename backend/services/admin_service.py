"""Admin read/write: stats, users, reports, analyses, subscriptions, views, mission control data."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import RESULTS_DIR
from models.db_models import Execution, Report, ReportView, Subscription, User


def get_stats(db: Session) -> dict:
    """Platform-wide stats for admin dashboard."""
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

    return {
        "total_users": total_users,
        "total_reports": total_reports,
        "total_analysis_runs": total_analysis_runs,
        "total_report_views": total_report_views,
        "total_subscriptions": total_subscriptions,
        "analyses_last_24h": analyses_last_24h,
        "analyses_last_7d": analyses_last_7d,
        "reports_last_24h": reports_last_24h,
        "reports_last_7d": reports_last_7d,
    }


def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get user by id. For admin add_tokens 404 check."""
    return db.query(User).filter(User.id == user_id).first()


def list_users(
    db: Session, limit: int, offset: int
) -> tuple[list[dict], int]:
    """List users with subscription count. Returns (list of user dicts, total)."""
    total = db.query(func.count(User.id)).scalar() or 0
    rows = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    user_ids = [u.id for u in rows]
    sub_counts = (
        db.query(Subscription.user_id, func.count(Subscription.id))
        .filter(Subscription.user_id.in_(user_ids))
        .group_by(Subscription.user_id)
    )
    count_by_user = {uid: c for uid, c in sub_counts}

    items = [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "token_balance": u.token_balance,
            "created_at": u.created_at,
            "subscription_count": count_by_user.get(u.id, 0),
        }
        for u in rows
    ]
    return items, total


def list_reports(db: Session, limit: int) -> tuple[list[dict], int]:
    """Latest reports with execution id and subject_id. Returns (items, total)."""
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
        items.append({
            "id": r.id,
            "ticker": subject_id or "",
            "analysis_run_id": ex_id or 0,
            "report_type": r.report_type,
            "created_at": r.created_at,
            "input_tokens": meta.get("input_tokens"),
            "output_tokens": meta.get("output_tokens"),
            "total_tokens": meta.get("total_tokens"),
            "cost_usd": meta.get("cost_usd"),
        })
    return items, total


def get_report_detail(db: Session, report_id: int) -> Optional[dict[str, Any]]:
    """Return one report with raw content and metadata for admin inspection."""
    row = (
        db.query(Report, Execution.id, Execution.subject_id)
        .outerjoin(Execution, Report.execution_id == Execution.id)
        .filter(Report.id == report_id)
        .first()
    )
    if not row:
        return None

    report, ex_id, subject_id = row
    metadata = None
    if report.metadata_json:
        try:
            metadata = json.loads(report.metadata_json) or {}
        except Exception:
            metadata = None

    meta_for_costs = metadata if isinstance(metadata, dict) else {}
    return {
        "id": report.id,
        "ticker": subject_id or "",
        "analysis_run_id": ex_id or 0,
        "report_type": report.report_type,
        "created_at": report.created_at,
        "content": report.content,
        "metadata": metadata,
        "metadata_raw": report.metadata_json,
        "input_tokens": meta_for_costs.get("input_tokens"),
        "output_tokens": meta_for_costs.get("output_tokens"),
        "total_tokens": meta_for_costs.get("total_tokens"),
        "cost_usd": meta_for_costs.get("cost_usd"),
    }


def list_analyses(db: Session, limit: int, offset: int) -> tuple[list[dict], int]:
    """Recent analysis runs with creator email and token/cost sums. Returns (items, total)."""
    total = db.query(func.count(Execution.id)).scalar() or 0
    rows = (
        db.query(Execution, User.email)
        .join(User, User.id == Execution.creator_id)
        .order_by(Execution.created_at.desc())
        .offset(offset)
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
        items.append({
            "id": ex.id,
            "ticker": ex.subject_id if ex.execution_type == "ticker" else (ex.subject_id or ""),
            "creator_id": ex.creator_id,
            "creator_email": email or "",
            "earned_tokens": ex.earned_tokens,
            "created_at": ex.created_at,
            "status": ex.status,
            "error_message": ex.error_message,
            "input_tokens": inp if inp else None,
            "output_tokens": out if out else None,
            "total_tokens": tot if tot else None,
            "cost_usd": round(cost, 6) if cost else None,
        })
    return items, total


def list_subscriptions(
    db: Session, limit: int, offset: int
) -> tuple[list[dict], int]:
    """List subscriptions with user email. Returns (items, total)."""
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
        {
            "id": s.id,
            "user_id": s.user_id,
            "user_email": email or "",
            "ticker": s.ticker,
            "email_updates": getattr(s, "email_updates", True),
            "created_at": s.created_at,
        }
        for s, email in rows
    ]
    return items, total


def get_views_for_run(
    db: Session, analysis_run_id: int, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Individual views for one analysis run. Returns (items, total)."""
    ex = db.query(Execution).filter(Execution.id == analysis_run_id).first()
    if not ex:
        return [], 0
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
        {
            "id": view.id,
            "ticker": ticker_upper,
            "analysis_run_id": ex.id,
            "viewer_id": view.viewer_id,
            "viewer_email": email or f"[deleted user id={view.viewer_id}]",
            "viewer_name": name,
            "viewed_at": view.viewed_at,
        }
        for view, email, name in rows
    ]
    return items, total


def get_views(db: Session, limit: int, offset: int) -> tuple[list[dict], int]:
    """All report views with viewer identity. Returns (items, total)."""
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
        {
            "id": view.id,
            "ticker": (ticker or "").upper(),
            "analysis_run_id": ex_id or 0,
            "viewer_id": view.viewer_id,
            "viewer_email": email or f"[deleted user id={view.viewer_id}]",
            "viewer_name": name,
            "viewed_at": view.viewed_at,
        }
        for view, ticker, ex_id, email, name in rows
    ]
    return items, total


def get_view_runs(db: Session, limit: int) -> tuple[list[dict], int]:
    """Runs with unique view counts. Returns (runs, total_runs_with_views)."""
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
    runs = [
        {
            "ticker": (ticker or "").upper(),
            "analysis_run_id": ex_id,
            "unique_views": int(unique_views or 0),
            "last_viewed_at": last_viewed_at,
        }
        for ticker, ex_id, unique_views, last_viewed_at in rows
        if last_viewed_at is not None
    ]
    return runs, total_runs_with_views


def get_views_daily(db: Session, days: int) -> list[dict]:
    """Count of report views per day for the last N days. Returns list of {date, count}."""
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
        result.append({"date": date_str, "count": count_val})
        current += timedelta(days=1)
    return result


def get_analyses_daily(db: Session, days: int) -> list[dict]:
    """Count of analysis runs per day for the last N days. Returns list of {date, count}."""
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
    today = date.today()
    start = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    count_by_day = {r.day: r.count for r in rows}  # type: ignore
    result = []
    current = start
    while current <= today:
        date_str = str(current)
        count_val = count_by_day.get(date_str, 0)  # type: ignore[arg-type]
        result.append({"date": date_str, "count": count_val})
        current += timedelta(days=1)
    return result


# --- Mission control (file + cache + DB) ---

_MAJOR_STOCKS_SECTORS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "major_stocks_sectors.json"
)


def _results_root() -> Path:
    p = Path(RESULTS_DIR)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parents[2] / p


def load_mission_control_entries(path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Load mission control ticker entries from JSON file."""
    from json import load as json_load
    p = path or _MAJOR_STOCKS_SECTORS_PATH
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json_load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, item in data.items():
        ticker_raw = key
        name = None
        sector = None
        industry = None
        quote_type = None
        market_cap = None

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
        entries.append({
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "industry": industry,
            "quote_type": quote_type,
            "market_cap": market_cap,
        })

    def _quote_type_sort_rank(qt: Optional[str]) -> int:
        return 0 if str(qt or "").strip().upper() == "EQUITY" else 1

    entries.sort(key=lambda item: (_quote_type_sort_rank(item.get("quote_type")), item["ticker"] or ""))
    return entries


def get_running_statuses_by_ticker(tickers: list[str]) -> dict[str, dict]:
    """Return currently running status payload keyed by ticker (from cache)."""
    from services.data_cache import list_running_analyses
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


def get_tickers_with_report_on_date(db: Session, date_str: str) -> set[str]:
    """Return set of ticker symbols that have a report for the given date (YYYY-MM-DD)."""
    from sqlalchemy import func
    rows = (
        db.query(Execution.subject_id)
        .join(Report, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            func.date(Execution.created_at) == date_str,
        )
        .distinct()
        .all()
    )
    return {str(r[0]).upper() for r in rows if r[0]}


def get_mission_control_items(db: Session) -> list[dict]:
    """
    Build mission control list: entries from file + last_completed from DB + running from cache.
    Returns list of dicts suitable for MissionControlTickerItem.
    """
    from services.data_cache import list_running_analyses

    mission_entries = load_mission_control_entries()
    mission_tickers = [str(item.get("ticker") or "").upper() for item in mission_entries if item.get("ticker")]
    ticker_set = set(mission_tickers)

    # Running statuses from cache
    allowed_tickers = {t.upper() for t in mission_tickers}
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

    # Last completed per ticker from DB with report counts and status
    last_completed = {}
    report_counts = {}
    execution_statuses = {}
    
    # Get the latest execution per ticker (completed or failed) using status and completed_at fields
    # We need to get the most recent execution for each ticker
    from sqlalchemy import and_
    
    # Subquery to get the latest execution ID per ticker
    latest_exec_subq = (
        db.query(
            Execution.subject_id,
            func.max(Execution.id).label("latest_id")
        )
        .filter(
            Execution.execution_type == "ticker",
            Execution.status.in_(["completed", "failed"])
        )
        .group_by(Execution.subject_id)
        .subquery()
    )
    
    # Get details of the latest executions
    for subject_id, completed_at, report_count, status in db.query(
        Execution.subject_id,
        Execution.completed_at,
        func.count(Report.id),
        Execution.status
    ).join(
        latest_exec_subq,
        and_(
            Execution.subject_id == latest_exec_subq.c.subject_id,
            Execution.id == latest_exec_subq.c.latest_id
        )
    ).join(
        Report, Report.execution_id == Execution.id, isouter=True
    ).group_by(
        Execution.subject_id, Execution.completed_at, Execution.status
    ).all():
        ticker_upper = str(subject_id).upper()
        if ticker_upper in ticker_set:
            if completed_at is not None:
                last_completed[ticker_upper] = completed_at
            report_counts[ticker_upper] = report_count
            execution_statuses[ticker_upper] = status

    # Get subscription counts per ticker
    subscription_counts = {}
    for ticker, count in db.query(
        Subscription.ticker,
        func.count(Subscription.id)
    ).filter(
        Subscription.ticker.in_(mission_tickers)
    ).group_by(
        Subscription.ticker
    ).all():
        ticker_upper = str(ticker).upper()
        subscription_counts[ticker_upper] = count

    def _calculate_priority(
        market_cap: Optional[float],
        subscription_count: int,
        last_completed_at: Optional[datetime],
        last_status: Optional[str]
    ) -> float:
        """
        Calculate priority score for rerunning analysis.
        Higher score = higher priority.
        Only considers stocks that have been executed at least once.
        
        Factors:
        1. Status bonus (0-50 points) - failed executions get high priority
        2. Market cap (normalized, 0-40 points)
        3. Subscription count (0-30 points)
        4. Days since last run (0-30 points, older = higher priority)
        
        Max score: 150 points
        Returns 0 for never-executed stocks.
        """
        # Never executed = 0 priority (excluded from consideration)
        if last_status is None:
            return 0.0
        
        score = 0.0
        
        # Status bonus (0-50 points)
        # Failed executions should be retried with high priority
        if last_status == "failed":
            score += 50.0  # High priority for failed runs
        # completed status gets 0 bonus (normal priority)
        
        # Market cap component (0-40 points)
        # Normalize market cap: $1B = 10 points, $100B = 20 points, $1T+ = 40 points
        if market_cap and market_cap > 0:
            import math
            # Log scale: log10(market_cap in billions)
            market_cap_billions = market_cap / 1_000_000_000
            if market_cap_billions > 0:
                log_cap = math.log10(market_cap_billions)
                # Scale: 0 (1B) to 3 (1T) -> 0 to 40 points
                score += min(40.0, max(0.0, log_cap * 13.33))
        
        # Subscription count component (0-30 points)
        # Linear scale: 1 sub = 3 points, 10+ subs = 30 points
        score += min(30.0, subscription_count * 3.0)
        
        # Days since last run component (0-30 points)
        # Linear scale: 1 day = 1 point, 30+ days = 30 points
        if last_completed_at:
            now = datetime.now(timezone.utc)
            # Ensure last_completed_at is timezone-aware
            if last_completed_at.tzinfo is None:
                last_completed_at = last_completed_at.replace(tzinfo=timezone.utc)
            days_since = (now - last_completed_at).total_seconds() / 86400
            score += min(30.0, max(0.0, days_since))
        else:
            # Has status but no completed_at (shouldn't happen, but handle gracefully)
            # Give moderate age priority
            score += 15.0
        
        return round(score, 2)

    def _quote_type_sort_rank(qt: Optional[str]) -> int:
        return 0 if str(qt or "").strip().upper() == "EQUITY" else 1

    def _entry_sort_key(entry: dict) -> tuple:
        ticker_upper = str(entry.get("ticker") or "").upper()
        completed_at = last_completed.get(ticker_upper)
        completed_ts = completed_at.timestamp() if completed_at is not None else 0.0
        return (
            _quote_type_sort_rank(entry.get("quote_type")),
            0 if completed_at is not None else 1,
            -completed_ts,
            ticker_upper,
        )

    items = []
    for entry in sorted(mission_entries, key=_entry_sort_key):
        ticker_upper = str(entry.get("ticker") or "").upper()
        if not ticker_upper:
            continue
        running = by_ticker.get(ticker_upper)
        sub_count = subscription_counts.get(ticker_upper, 0)
        last_completed_at = last_completed.get(ticker_upper)
        last_status = execution_statuses.get(ticker_upper)
        priority = _calculate_priority(
            entry.get("market_cap"),
            sub_count,
            last_completed_at,
            last_status
        )
        items.append({
            "ticker": ticker_upper,
            "name": entry.get("name"),
            "quote_type": entry.get("quote_type"),
            "market_cap": entry.get("market_cap"),
            "last_completed_at": last_completed_at,
            "report_count": report_counts.get(ticker_upper),
            "sector": entry.get("sector"),
            "industry": entry.get("industry"),
            "is_running": running is not None,
            "running_analysis_id": running.get("analysis_run_id") if running else None,
            "subscription_count": sub_count,
            "priority_score": priority,
            "last_status": execution_statuses.get(ticker_upper),
        })
    return items

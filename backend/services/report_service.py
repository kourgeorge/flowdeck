"""Service to read and write reports via SQLite."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

from services.key_takeaways import extract_key_takeaways
from database import SessionLocal
from models.db_models import Report, AnalysisRun


def _date_part(run_id_or_date: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD from run id (YYYY-MM-DD_HH-MM-SS) or return as-is if already date-only."""
    if not run_id_or_date:
        return None
    if "_" in run_id_or_date:
        return run_id_or_date.split("_")[0]
    return run_id_or_date


def _days_ago(report_date: Optional[str], generated_at: Optional[str]) -> Optional[int]:
    ref = None
    if generated_at:
        try:
            ref = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if ref is None and report_date:
        try:
            date_part = _date_part(report_date)
            if date_part:
                ref = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass
    if ref is None:
        return None
    return max(0, (datetime.now(timezone.utc) - ref).days)


def _report_row_to_dict(row: Report, date: str) -> Dict[str, Any]:
    """Convert a Report row to the dict format expected by callers."""
    meta = {}
    if row.metadata_json:
        try:
            meta = json.loads(row.metadata_json) or {}
        except Exception:
            pass
    content = row.content or ""
    analysis_date = meta.get("analysis_date") or date
    key_takeaways = meta.get("key_takeaways")
    if not key_takeaways and content:
        key_takeaways = extract_key_takeaways(content)
    out = {
        "content": content,
        "score": meta.get("score"),
        "score_label": meta.get("score_label"),
        "key_takeaways": key_takeaways or [],
        "analysis_date": analysis_date,
        "generated_at": meta.get("generated_at"),
        "days_ago": _days_ago(analysis_date, meta.get("generated_at")) or _days_ago(analysis_date, None),
        "recommendation": meta.get("recommendation"),
        "expected_return_pct": meta.get("expected_return_pct"),
        "bear_case_return_pct": meta.get("bear_case_return_pct"),
        "bull_case_return_pct": meta.get("bull_case_return_pct"),
        "confidence": meta.get("confidence"),
        "models_used": meta.get("models_used"),
    }
    if meta.get("bull_viewpoint") is not None:
        out["bull_viewpoint"] = meta["bull_viewpoint"]
    if meta.get("bear_viewpoint") is not None:
        out["bear_viewpoint"] = meta["bear_viewpoint"]
    if meta.get("risky_viewpoint") is not None:
        out["risky_viewpoint"] = meta["risky_viewpoint"]
    if meta.get("safe_viewpoint") is not None:
        out["safe_viewpoint"] = meta["safe_viewpoint"]
    if meta.get("neutral_viewpoint") is not None:
        out["neutral_viewpoint"] = meta["neutral_viewpoint"]
    if meta.get("tps_plan") is not None:
        out["tps_plan"] = meta["tps_plan"]
    return out


_EMPTY = {
    "content": None, "score": None, "score_label": None, "key_takeaways": [],
    "analysis_date": None, "generated_at": None, "days_ago": None,
    "recommendation": None, "expected_return_pct": None, "bear_case_return_pct": None,
    "bull_case_return_pct": None, "confidence": None,
}


def save_report(
    ticker: str,
    report_type: str,
    analysis_run_id: int,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Save or upsert a report into the database. Requires analysis_run_id."""
    meta = metadata or {}
    metadata_json = json.dumps(meta) if meta else None
    db = SessionLocal()
    try:
        row = (
            db.query(Report)
            .filter(
                Report.analysis_run_id == analysis_run_id,
                Report.report_type == report_type,
            )
            .first()
        )
        if row:
            row.content = content or ""
            row.metadata_json = metadata_json
            row.ticker = ticker.upper()
            action = "updated"
        else:
            row = Report(
                ticker=ticker.upper(),
                report_type=report_type,
                content=content or "",
                metadata_json=metadata_json,
                analysis_run_id=analysis_run_id,
            )
            db.add(row)
            action = "inserted"
        db.commit()
        logger.debug(
            "Report %s ticker=%s analysis_run_id=%s report_type=%s",
            action, ticker.upper(), analysis_run_id, report_type,
        )
    except Exception as e:
        logger.exception(
            "Failed to save report ticker=%s analysis_run_id=%s report_type=%s error=%s",
            ticker, analysis_run_id, report_type, e,
        )
        raise
    finally:
        db.close()


class ReportService:
    """Service to read reports from SQLite database."""

    def __init__(self) -> None:
        pass

    def get_latest_analysis_run(self, ticker: str) -> Optional[tuple[int, str]]:
        """Return (analysis_run_id, date_display) for the most recent run, or None."""
        db = SessionLocal()
        try:
            row = (
                db.query(AnalysisRun.id, AnalysisRun.created_at)
                .join(Report, Report.analysis_run_id == AnalysisRun.id)
                .filter(Report.ticker == ticker.upper())
                .order_by(AnalysisRun.id.desc())
                .first()
            )
            if not row:
                return None
            ar_id, created = row
            date_display = created.strftime("%Y-%m-%d %H:%M") if created else str(ar_id)
            return (ar_id, date_display)
        finally:
            db.close()

    def has_report_for_date(self, ticker: str, date: str) -> bool:
        """date is YYYY-MM-DD; matches any run where date(created_at) = date."""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            ticker_upper = ticker.upper()
            return (
                db.query(Report)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(Report.ticker == ticker_upper, func.date(AnalysisRun.created_at) == date)
                .limit(1)
                .count()
            ) > 0
        finally:
            db.close()

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        """date is YYYY-MM-DD; returns tickers with any run that day."""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            rows = (
                db.query(Report.ticker)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(func.date(AnalysisRun.created_at) == date)
                .distinct()
                .all()
            )
            return [r.ticker for r in rows]
        finally:
            db.close()

    def get_tickers_with_reports_for_date_paginated(
        self, date: str, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        """Tickers with reports for date, ordered by recency (newest first). Returns (ticker_list, total_count)."""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            rows = (
                db.query(Report.ticker, AnalysisRun.id)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(func.date(AnalysisRun.created_at) == date)
                .order_by(AnalysisRun.id.desc())
                .all()
            )
            seen: set[str] = set()
            ordered_tickers: List[str] = []
            for r in rows:
                t = r.ticker.upper()
                if t not in seen:
                    seen.add(t)
                    ordered_tickers.append(t)
            total = len(ordered_tickers)
            tickers = ordered_tickers[offset : offset + limit]
            return (tickers, total)
        finally:
            db.close()

    def _recent_date_window_bounds(self, end_date: str, days: int) -> Optional[tuple[str, str]]:
        """Return [start, end) date bounds for the N-day window ending on end_date."""
        date_part = _date_part(end_date) or end_date
        try:
            end_day = datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            return None
        start_day = end_day - timedelta(days=max(1, days) - 1)
        start_bound = start_day.strftime("%Y-%m-%d")
        end_exclusive = (end_day + timedelta(days=1)).strftime("%Y-%m-%d")
        return (start_bound, end_exclusive)

    def get_tickers_with_reports_for_recent_days(self, end_date: str, days: int) -> List[str]:
        """Tickers with reports in the last N days (inclusive), ordered by recency."""
        if days <= 1:
            return self.get_tickers_with_reports_for_date(end_date)

        bounds = self._recent_date_window_bounds(end_date, days)
        if bounds is None:
            return self.get_tickers_with_reports_for_date(end_date)

        start_bound, end_exclusive = bounds
        db = SessionLocal()
        try:
            from sqlalchemy import func
            rows = (
                db.query(Report.ticker, AnalysisRun.id)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(
                    func.date(AnalysisRun.created_at) >= start_bound,
                    func.date(AnalysisRun.created_at) < end_exclusive,
                )
                .order_by(AnalysisRun.id.desc())
                .all()
            )
            seen: set[str] = set()
            ordered_tickers: List[str] = []
            for r in rows:
                t = r.ticker.upper()
                if t not in seen:
                    seen.add(t)
                    ordered_tickers.append(t)
            return ordered_tickers
        finally:
            db.close()

    def get_tickers_with_reports_for_recent_days_paginated(
        self, end_date: str, days: int, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        """Paginated tickers with reports in the last N days (inclusive), ordered by recency."""
        if days <= 1:
            return self.get_tickers_with_reports_for_date_paginated(end_date, limit, offset)

        bounds = self._recent_date_window_bounds(end_date, days)
        if bounds is None:
            return self.get_tickers_with_reports_for_date_paginated(end_date, limit, offset)

        start_bound, end_exclusive = bounds
        db = SessionLocal()
        try:
            from sqlalchemy import func
            rows = (
                db.query(Report.ticker, AnalysisRun.id)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(
                    func.date(AnalysisRun.created_at) >= start_bound,
                    func.date(AnalysisRun.created_at) < end_exclusive,
                )
                .order_by(AnalysisRun.id.desc())
                .all()
            )
            seen: set[str] = set()
            ordered_tickers: List[str] = []
            for r in rows:
                t = r.ticker.upper()
                if t not in seen:
                    seen.add(t)
                    ordered_tickers.append(t)
            total = len(ordered_tickers)
            tickers = ordered_tickers[offset : offset + limit]
            return (tickers, total)
        finally:
            db.close()

    def get_reports_with_scores(self, ticker: str, analysis_run_id: int) -> Dict[str, Dict[str, Any]]:
        """Returns report_type -> dict with content, score, etc. for the given analysis run."""
        db = SessionLocal()
        try:
            ticker_upper = ticker.upper()
            rows = (
                db.query(Report)
                .join(AnalysisRun, Report.analysis_run_id == AnalysisRun.id)
                .filter(Report.ticker == ticker_upper, Report.analysis_run_id == analysis_run_id)
                .all()
            )
            date_str = None
            if rows:
                ar = db.query(AnalysisRun).filter(AnalysisRun.id == analysis_run_id).first()
                date_str = ar.created_at.strftime("%Y-%m-%d") if ar and ar.created_at else str(analysis_run_id)
            result = {}
            for row in rows:
                result[row.report_type] = _report_row_to_dict(row, date_str or str(analysis_run_id))
            return result
        finally:
            db.close()

    def get_reports_for_run(self, ticker: str, analysis_run_id: int) -> Dict[str, Optional[str]]:
        scores = self.get_reports_with_scores(ticker, analysis_run_id)
        return {k: (v.get("content") or "") for k, v in scores.items()}

    def get_latest_reports(self, ticker: str) -> Dict[str, Optional[str]]:
        latest = self.get_latest_analysis_run(ticker)
        return self.get_reports_for_run(ticker, latest[0]) if latest else {}

    def get_historical_analyses(self, ticker: str) -> List[Dict]:
        """Returns list of {analysis_run_id, date, available_reports} for each run, ordered by analysis_runs.created_at newest first. Display date is from the same source."""
        db = SessionLocal()
        try:
            rows = (
                db.query(AnalysisRun.id, AnalysisRun.created_at, Report.report_type)
                .join(Report, Report.analysis_run_id == AnalysisRun.id)
                .filter(Report.ticker == ticker.upper())
                .all()
            )
            # by_run: ar_id -> (created_at, date_str, report_types); created_at is the single source for display and sort
            by_run: Dict[int, tuple[Optional[datetime], str, List[str]]] = {}
            for ar_id, created, report_type in rows:
                if ar_id not in by_run:
                    date_str = created.strftime("%Y-%m-%d %H:%M") if created else str(ar_id)
                    by_run[ar_id] = (created, date_str, [])
                by_run[ar_id][2].append(report_type)
            analyses = [
                {"analysis_run_id": ar_id, "date": date_str, "available_reports": sorted(report_types)}
                for ar_id, (_created, date_str, report_types) in by_run.items()
            ]
            # Sort by analysis_runs.created_at descending so order matches displayed dates
            analyses.sort(
                key=lambda x: by_run[x["analysis_run_id"]][0] or datetime.min,
                reverse=True,
            )
            return analyses
        finally:
            db.close()

    def has_reports(self, ticker: str) -> bool:
        return self.get_latest_analysis_run(ticker) is not None

    def list_report_dates(self, ticker: str) -> List[str]:
        """Return list of date strings (YYYY-MM-DD) for runs that have reports, newest first."""
        hist = self.get_historical_analyses(ticker)
        return [h["date"] for h in hist]

    def get_analysis_run_for_date(self, ticker: str, date_str: str) -> Optional[tuple[int, str]]:
        """Resolve date (YYYY-MM-DD or analysis_run_id as string) to (analysis_run_id, date_display)."""
        hist = self.get_historical_analyses(ticker)
        if not hist:
            return None
        # Exact analysis_run_id match (user passed numeric id as string)
        try:
            ar_id = int(date_str)
            for h in hist:
                if h["analysis_run_id"] == ar_id:
                    return (ar_id, h["date"])
            return None
        except ValueError:
            pass
        # Date match: YYYY-MM-DD exact or prefix (hist is newest first)
        for h in hist:
            if h["date"] == date_str or h["date"].startswith(date_str):
                return (h["analysis_run_id"], h["date"])
        return None

    def get_report_content(self, ticker: str, analysis_run_id: int, report_type: str) -> Optional[str]:
        """Return raw content for one report type, or None if not found."""
        reports = self.get_reports_for_run(ticker, analysis_run_id)
        return reports.get(report_type) or None

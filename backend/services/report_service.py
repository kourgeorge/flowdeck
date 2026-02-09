"""Service to read and write reports via SQLite."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

from services.key_takeaways import extract_key_takeaways
from database import SessionLocal
from models.db_models import Report


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
    return out


_EMPTY = {
    "content": None, "score": None, "score_label": None, "key_takeaways": [],
    "analysis_date": None, "generated_at": None, "days_ago": None,
    "recommendation": None, "expected_return_pct": None, "bear_case_return_pct": None,
    "bull_case_return_pct": None, "confidence": None,
}


def save_report(
    ticker: str,
    run_id: str,
    report_type: str,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Save or upsert a report into the database."""
    meta = metadata or {}
    metadata_json = json.dumps(meta) if meta else None
    db = SessionLocal()
    try:
        row = (
            db.query(Report)
            .filter(
                Report.ticker == ticker.upper(),
                Report.run_id == run_id,
                Report.report_type == report_type,
            )
            .first()
        )
        if row:
            row.content = content or ""
            row.metadata_json = metadata_json
            action = "updated"
        else:
            row = Report(
                ticker=ticker.upper(),
                run_id=run_id,
                report_type=report_type,
                content=content or "",
                metadata_json=metadata_json,
            )
            db.add(row)
            action = "inserted"
        db.commit()
        logger.debug(
            "Report %s ticker=%s run_id=%s report_type=%s",
            action, ticker.upper(), run_id, report_type,
        )
    except Exception as e:
        logger.exception(
            "Failed to save report ticker=%s run_id=%s report_type=%s error=%s",
            ticker, run_id, report_type, e,
        )
        raise
    finally:
        db.close()


class ReportService:
    """Service to read reports from SQLite database."""

    def __init__(self, results_dir: str = None):
        """results_dir is ignored; kept for backward compatibility with sync_major_stocks etc."""
        pass

    def get_latest_report_date(self, ticker: str) -> Optional[str]:
        db = SessionLocal()
        try:
            row = (
                db.query(Report.run_id)
                .filter(Report.ticker == ticker.upper())
                .order_by(Report.run_id.desc())
                .first()
            )
            return row.run_id if row else None
        finally:
            db.close()

    def has_report_for_date(self, ticker: str, date: str) -> bool:
        """date can be YYYY-MM-DD (match any run that day) or full run id YYYY-MM-DD_HH-MM-SS (exact)."""
        db = SessionLocal()
        try:
            ticker_upper = ticker.upper()
            if "_" in date:
                count = (
                    db.query(Report)
                    .filter(Report.ticker == ticker_upper, Report.run_id == date)
                    .limit(1)
                    .count()
                )
                return count > 0
            # Match any run that starts with date (YYYY-MM-DD)
            count = (
                db.query(Report)
                .filter(
                    Report.ticker == ticker_upper,
                    Report.run_id.like(f"{date}%"),
                )
                .limit(1)
                .count()
            )
            return count > 0
        finally:
            db.close()

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        """date can be YYYY-MM-DD (tickers with any run that day) or full run id (exact)."""
        db = SessionLocal()
        try:
            if "_" in date:
                rows = db.query(Report.ticker).filter(Report.run_id == date).distinct().all()
            else:
                rows = db.query(Report.ticker).filter(Report.run_id.like(f"{date}%")).distinct().all()
            return [r.ticker for r in rows]
        finally:
            db.close()

    def get_reports_with_scores(self, ticker: str, date: str) -> Dict[str, Dict[str, Any]]:
        """date can be YYYY-MM-DD or full run id. Returns report_type -> dict with content, score, etc."""
        db = SessionLocal()
        try:
            ticker_upper = ticker.upper()
            run_id = date
            if "_" not in date:
                # Find latest run_id that starts with this date
                latest = (
                    db.query(Report.run_id)
                    .filter(Report.ticker == ticker_upper, Report.run_id.like(f"{date}%"))
                    .order_by(Report.run_id.desc())
                    .first()
                )
                run_id = latest.run_id if latest else date
            rows = db.query(Report).filter(Report.ticker == ticker_upper, Report.run_id == run_id).all()
            result = {}
            for row in rows:
                result[row.report_type] = _report_row_to_dict(row, row.run_id)
            return result
        finally:
            db.close()

    def get_reports_for_date(self, ticker: str, date: str) -> Dict[str, Optional[str]]:
        scores = self.get_reports_with_scores(ticker, date)
        return {k: (v.get("content") or "") for k, v in scores.items()}

    def get_latest_reports(self, ticker: str) -> Dict[str, Optional[str]]:
        d = self.get_latest_report_date(ticker)
        return self.get_reports_for_date(ticker, d) if d else {}

    def get_historical_analyses(self, ticker: str) -> List[Dict]:
        db = SessionLocal()
        try:
            rows = (
                db.query(Report.run_id, Report.report_type)
                .filter(Report.ticker == ticker.upper())
                .all()
            )
            by_run: Dict[str, List[str]] = {}
            for run_id, report_type in rows:
                if run_id not in by_run:
                    by_run[run_id] = []
                by_run[run_id].append(report_type)
            analyses = [
                {"date": run_id, "available_reports": sorted(report_types)}
                for run_id, report_types in by_run.items()
            ]
            analyses.sort(key=lambda x: x["date"], reverse=True)
            return analyses
        finally:
            db.close()

    def has_reports(self, ticker: str) -> bool:
        return self.get_latest_report_date(ticker) is not None

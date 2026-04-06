"""Service to read and write reports via SQLite."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

from database import SessionLocal
from models.db_models import Report, Execution


def update_execution_status(
    execution_id: int,
    status: str,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """
    Update execution status. Creates its own DB session.
    
    Args:
        execution_id: The execution ID to update
        status: One of 'running', 'completed', 'failed'
        error_message: Optional error message for failed executions
        completed_at: Optional completion timestamp (defaults to now if not provided and status is completed/failed)
    """
    db = SessionLocal()
    try:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if execution:
            execution.status = status  # type: ignore
            if error_message is not None:
                execution.error_message = error_message  # type: ignore
            if completed_at is not None:
                execution.completed_at = completed_at  # type: ignore
            elif status in ("completed", "failed"):
                # Auto-set completed_at if not provided
                execution.completed_at = datetime.utcnow()  # type: ignore
            db.commit()
            logger.debug(
                "Execution status updated execution_id=%s status=%s",
                execution_id, status,
            )
        else:
            logger.warning(
                "Execution not found for status update execution_id=%s",
                execution_id,
            )
    except Exception as e:
        logger.exception(
            "Failed to update execution status execution_id=%s status=%s error=%s",
            execution_id, status, e,
        )
        db.rollback()
        raise
    finally:
        db.close()


def aggregate_llm_usage_from_reports(execution_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    Aggregate LLM usage statistics from all reports for an execution.
    
    Returns a dict with:
        - input_tokens: Total input tokens across all reports
        - output_tokens: Total output tokens across all reports
        - total_tokens: Total tokens (input + output)
        - cost_usd: Total cost in USD
        - models_used: Dict with provider and model info (from first report)
        - report_count: Number of reports with usage data
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
    
    try:
        reports = (
            db.query(Report)
            .filter(Report.execution_id == execution_id)
            .all()
        )
        
        total_input = 0
        total_output = 0
        total_cost = 0.0
        models_used = None
        report_count = 0
        
        for report in reports:
            if not report.metadata_json:
                continue
            
            try:
                metadata = json.loads(report.metadata_json)
            except Exception:
                continue
            
            # Extract token counts
            input_tokens = metadata.get("input_tokens")
            output_tokens = metadata.get("output_tokens")
            cost_usd = metadata.get("cost_usd")
            
            if input_tokens is not None:
                total_input += int(input_tokens)
                report_count += 1
            if output_tokens is not None:
                total_output += int(output_tokens)
            if cost_usd is not None:
                total_cost += float(cost_usd)
            
            # Capture models_used from first report that has it
            if models_used is None and metadata.get("models_used"):
                models_used = metadata["models_used"]
        
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "cost_usd": round(total_cost, 6),
            "models_used": models_used,
            "report_count": report_count,
        }
    finally:
        if should_close:
            db.close()


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
    key_takeaways = meta.get("key_takeaways") or []
    out = {
        "content": content,
        "score": meta.get("score"),
        "score_label": meta.get("score_label"),
        "key_takeaways": key_takeaways,
        "analysis_date": analysis_date,
        "generated_at": meta.get("generated_at"),
        "days_ago": _days_ago(analysis_date, meta.get("generated_at")) or _days_ago(analysis_date, None),
        "recommendation": meta.get("recommendation"),
        "expected_return_pct": meta.get("expected_return_pct"),
        "bear_case_return_pct": meta.get("bear_case_return_pct"),
        "bull_case_return_pct": meta.get("bull_case_return_pct"),
        "current_price": meta.get("current_price"),
        "currency": meta.get("currency"),
        "confidence": meta.get("confidence"),
        "models_used": meta.get("models_used"),
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "total_tokens": meta.get("total_tokens"),
        "cost_usd": meta.get("cost_usd"),
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
    out["resources"] = meta.get("resources") or []
    out["agent_steps"] = meta.get("agent_steps") or []
    return out


_EMPTY = {
    "content": None, "score": None, "score_label": None, "key_takeaways": [],
    "analysis_date": None, "generated_at": None, "days_ago": None,
    "recommendation": None, "expected_return_pct": None, "bear_case_return_pct": None,
    "bull_case_return_pct": None, "current_price": None, "currency": None, "confidence": None,
}


def save_report(
    execution_id: int,
    report_type: str,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Save or upsert a report by (execution_id, report_type)."""
    meta = metadata or {}
    metadata_json = json.dumps(meta) if meta else None
    db = SessionLocal()
    try:
        row = (
            db.query(Report)
            .filter(
                Report.execution_id == execution_id,
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
                execution_id=execution_id,
                report_type=report_type,
                content=content or "",
                metadata_json=metadata_json,
            )
            db.add(row)
            action = "inserted"
        db.commit()
        logger.debug(
            "Report %s execution_id=%s report_type=%s",
            action, execution_id, report_type,
        )
    except Exception as e:
        logger.exception(
            "Failed to save report execution_id=%s report_type=%s error=%s",
            execution_id, report_type, e,
        )
        raise
    finally:
        db.close()


class ReportService:
    """Service to read reports from SQLite database."""

    def __init__(self) -> None:
        pass

    def get_latest_execution(
        self, execution_type: str, subject_type: str, subject_id: str
    ) -> Optional[tuple[int, str]]:
        """Return (execution_id, date_display) for the most recent run, or None."""
        db = SessionLocal()
        try:
            row = (
                db.query(Execution.id, Execution.created_at)
                .filter(
                    Execution.execution_type == execution_type,
                    Execution.subject_type == subject_type,
                    Execution.subject_id == subject_id,
                )
                .order_by(Execution.created_at.desc())
                .first()
            )
            if not row:
                return None
            ex_id, created = row
            date_display = created.strftime("%Y-%m-%d %H:%M") if created else str(ex_id)
            return (ex_id, date_display)
        finally:
            db.close()

    def get_latest_execution_for_ticker(self, ticker: str) -> Optional[tuple[int, str]]:
        """Return (execution_id, date_display) for the latest ticker run, or None."""
        return self.get_latest_execution("ticker", "ticker", ticker.upper())

    def has_report_for_date(self, ticker: str, date: str) -> bool:
        """date is YYYY-MM-DD; matches any run where date(created_at) = date."""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            return (
                db.query(Report)
                .join(Execution, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    Execution.subject_id == ticker.upper(),
                    func.date(Execution.created_at) == date,
                )
                .limit(1)
                .count()
            ) > 0
        finally:
            db.close()

    def get_tickers_with_reports_for_date(self, date: str) -> List[str]:
        """date is YYYY-MM-DD; returns tickers with any run that day."""
        db = SessionLocal()
        try:
            from sqlalchemy import func, distinct
            rows = (
                db.query(distinct(Execution.subject_id))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) == date,
                )
                .all()
            )
            return [str(r[0]).upper() for r in rows if r[0]]
        finally:
            db.close()

    def get_tickers_with_reports_for_date_paginated(
        self, date: str, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        """Return paginated tickers with reports for a specific date."""
        db = SessionLocal()
        try:
            from sqlalchemy import func, distinct
            
            # Get total count
            total_count = (
                db.query(func.count(distinct(Execution.subject_id)))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) == date,
                )
                .scalar()
            ) or 0
            
            # Get paginated results
            rows = (
                db.query(distinct(Execution.subject_id))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) == date,
                )
                .limit(limit)
                .offset(offset)
                .all()
            )
            tickers = [str(r[0]).upper() for r in rows if r[0]]
            return (tickers, total_count)
        finally:
            db.close()

    def get_reports_for_execution(
        self, execution_id: int
    ) -> Dict[str, Dict[str, Any]]:
        """Return all reports for an execution as {report_type: report_dict}."""
        db = SessionLocal()
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                return {}
            
            date_display = execution.created_at.strftime("%Y-%m-%d") if execution.created_at else ""
            
            reports = (
                db.query(Report)
                .filter(Report.execution_id == execution_id)
                .all()
            )
            
            result = {}
            for report in reports:
                result[report.report_type] = _report_row_to_dict(report, date_display)
            
            return result
        finally:
            db.close()

    def get_report(
        self, execution_id: int, report_type: str
    ) -> Optional[Dict[str, Any]]:
        """Return a single report or None."""
        db = SessionLocal()
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                return None
            
            date_display = execution.created_at.strftime("%Y-%m-%d") if execution.created_at else ""
            
            report = (
                db.query(Report)
                .filter(
                    Report.execution_id == execution_id,
                    Report.report_type == report_type,
                )
                .first()
            )
            
            if not report:
                return None
            
            return _report_row_to_dict(report, date_display)
        finally:
            db.close()

    def get_reports_for_run(self, execution_id: int) -> Dict[str, Optional[str]]:
        """Return all reports for an execution as {report_type: content_string}."""
        db = SessionLocal()
        try:
            reports = (
                db.query(Report)
                .filter(Report.execution_id == execution_id)
                .all()
            )
            
            result = {}
            for report in reports:
                result[report.report_type] = report.content
            
            return result
        finally:
            db.close()

    def get_reports_with_scores(self, execution_id: int) -> Dict[str, Dict[str, Any]]:
        """Return all reports for an execution with full metadata (alias for get_reports_for_execution)."""
        return self.get_reports_for_execution(execution_id)

    def get_analysis_run_for_date(
        self, ticker: str, date_str: str
    ) -> Optional[tuple[int, str]]:
        """Return (execution_id, date_display) for a specific date, or None."""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            row = (
                db.query(Execution.id, Execution.created_at)
                .filter(
                    Execution.execution_type == "ticker",
                    Execution.subject_type == "ticker",
                    Execution.subject_id == ticker.upper(),
                    func.date(Execution.created_at) == date_str,
                )
                .order_by(Execution.created_at.desc())
                .first()
            )
            if not row:
                return None
            ex_id, created = row
            date_display = created.strftime("%Y-%m-%d %H:%M") if created else str(ex_id)
            return (ex_id, date_display)
        finally:
            db.close()

    def get_historical_analyses(self, ticker: str) -> List[Dict[str, Any]]:
        """Return list of historical analysis runs for a ticker with available reports."""
        db = SessionLocal()
        try:
            # Get all executions with their reports
            rows = (
                db.query(Execution.id, Execution.created_at, Report.report_type)
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    Execution.subject_type == "ticker",
                    Execution.subject_id == ticker.upper(),
                )
                .all()
            )
            
            # Group by execution_id
            by_run: Dict[int, tuple[Optional[Any], List[str]]] = {}
            for ex_id, created, report_type in rows:
                if ex_id not in by_run:
                    by_run[ex_id] = (created, [])
                by_run[ex_id][1].append(report_type)
            
            # Build result list
            result = []
            for ex_id, (created, report_types) in by_run.items():
                date_str = created.strftime("%Y-%m-%d") if created else ""
                date_display = created.strftime("%Y-%m-%d %H:%M") if created else str(ex_id)
                result.append({
                    "analysis_run_id": ex_id,
                    "date": date_str,
                    "date_display": date_display,
                    "available_reports": report_types,
                })
            
            # Sort by date descending
            result.sort(key=lambda x: x["date"], reverse=True)
            
            return result
        finally:
            db.close()

    def list_report_dates(self, ticker: str) -> List[str]:
        """Return list of dates (YYYY-MM-DD) that have reports for this ticker."""
        db = SessionLocal()
        try:
            from sqlalchemy import func, distinct
            rows = (
                db.query(distinct(func.date(Execution.created_at)))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    Execution.subject_id == ticker.upper(),
                )
                .order_by(func.date(Execution.created_at).desc())
                .all()
            )
            return [str(r[0]) for r in rows if r[0]]
        finally:
            db.close()

    def get_tickers_with_reports_for_recent_days(
        self, end_date: str, days: int
    ) -> List[str]:
        """Return tickers with reports in the last N days ending on end_date."""
        db = SessionLocal()
        try:
            from sqlalchemy import func, distinct
            from datetime import datetime, timedelta
            
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days - 1)
            
            rows = (
                db.query(distinct(Execution.subject_id))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) >= start_dt.strftime("%Y-%m-%d"),
                    func.date(Execution.created_at) <= end_date,
                )
                .all()
            )
            return [str(r[0]).upper() for r in rows if r[0]]
        finally:
            db.close()

    def get_tickers_with_reports_for_recent_days_paginated(
        self, end_date: str, days: int, limit: int, offset: int = 0
    ) -> tuple[List[str], int]:
        """Return paginated tickers with reports in the last N days ending on end_date."""
        db = SessionLocal()
        try:
            from sqlalchemy import func, distinct
            from datetime import datetime, timedelta
            
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=days - 1)
            
            # Get total count
            total_count = (
                db.query(func.count(distinct(Execution.subject_id)))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) >= start_dt.strftime("%Y-%m-%d"),
                    func.date(Execution.created_at) <= end_date,
                )
                .scalar()
            ) or 0
            
            # Get paginated results
            rows = (
                db.query(distinct(Execution.subject_id))
                .join(Report, Report.execution_id == Execution.id)
                .filter(
                    Execution.execution_type == "ticker",
                    func.date(Execution.created_at) >= start_dt.strftime("%Y-%m-%d"),
                    func.date(Execution.created_at) <= end_date,
                )
                .limit(limit)
                .offset(offset)
                .all()
            )
            tickers = [str(r[0]).upper() for r in rows if r[0]]
            return (tickers, total_count)
        finally:
            db.close()

# Made with Bob

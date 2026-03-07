"""Sync routine: ensure each major stock has a report for today."""

import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from config import MAJOR_TICKERS, RESULTS_DIR
from database import SessionLocal
from services.report_service import ReportService
from services.analysis_service import AnalysisService
from services import token_service


def get_missing_and_skipped(
    analysis_date: str = None,
) -> Tuple[List[str], List[str]]:
    """
    Return (tickers_without_report, tickers_with_report) for the given date.
    Uses MAJOR_STOCKS and ReportService.has_report_for_date.
    """
    if analysis_date is None:
        analysis_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_service = ReportService()
    triggered: List[str] = []
    skipped: List[str] = []
    for ticker in MAJOR_TICKERS:
        t = ticker.upper()
        if report_service.has_report_for_date(ticker, analysis_date):
            skipped.append(t)
        else:
            triggered.append(t)
    return (triggered, skipped)


def run_analyses_for_tickers(
    tickers: List[str],
    analysis_date: str,
    analysis_service: AnalysisService,
    db: Session,
    creator_id: Optional[int] = None,
    analysts: List[str] = None,
    research_depth: int = 5,
    llm_provider: str = "azure",
    wait_for_completion: bool = True,
    poll_interval_seconds: float = 10.0,
    completion_timeout_seconds: float = 3600.0,
) -> None:
    """
    Start analysis for each ticker in tickers, sequentially. Optionally wait for each to complete.
    Records each new run in analysis_runs (using creator_id or system user).
    """
    if analysts is None:
        analysts = ["market", "news", "fundamentals", "technical"]
    if creator_id is None:
        creator_id = token_service.get_system_user_id(db)
    for ticker in tickers:
        run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        analysis_run_id = token_service.record_analysis_run(creator_id, ticker, run_id, db)
        analysis_id, existing = analysis_service.start_analysis(
            ticker=ticker,
            analysis_date=analysis_date,
            analysts=analysts,
            research_depth=research_depth,
            llm_provider=llm_provider,
            progress_callback=None,
            run_id=run_id,
            analysis_run_id=analysis_run_id,
        )
        if existing:
            token_service.delete_analysis_run(creator_id, ticker, run_id, db)
        if wait_for_completion:
            _wait_for_analysis(
                analysis_service,
                analysis_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=completion_timeout_seconds,
            )


def run_sync(
    analysis_date: str = None,
    analysts: List[str] = None,
    research_depth: int = 5,
    llm_provider: str = "azure",
    wait_for_completion: bool = True,
    poll_interval_seconds: float = 10.0,
    completion_timeout_seconds: float = 3600.0,
) -> dict:
    """
    For each major stock, if no report exists for the given date, trigger an analysis.
    Runs analyses sequentially (waits for each to complete before starting the next).

    Returns:
        dict with keys: date, triggered (list of tickers started), skipped (list already had report).
    """
    if analysis_date is None:
        analysis_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    triggered, skipped = get_missing_and_skipped(analysis_date)
    if not triggered:
        return {"date": analysis_date, "triggered": [], "skipped": skipped}
    analysis_service = AnalysisService(results_dir=RESULTS_DIR)
    if analysts is None:
        analysts = ["market", "news", "fundamentals", "technical"]
    db = SessionLocal()
    try:
        run_analyses_for_tickers(
            tickers=triggered,
            analysis_date=analysis_date,
            analysis_service=analysis_service,
            db=db,
            creator_id=None,
            analysts=analysts,
            research_depth=research_depth,
            llm_provider=llm_provider,
            wait_for_completion=wait_for_completion,
            poll_interval_seconds=poll_interval_seconds,
            completion_timeout_seconds=completion_timeout_seconds,
        )
    finally:
        db.close()
    return {
        "date": analysis_date,
        "triggered": triggered,
        "skipped": skipped,
    }


def _wait_for_analysis(
    analysis_service: AnalysisService,
    analysis_id: str,
    poll_interval_seconds: float = 10.0,
    timeout_seconds: float = 3600.0,
) -> None:
    """Poll analysis status until completed, error, or timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status_info = analysis_service.get_analysis_status(analysis_id)
        if status_info is None:
            return
        st = status_info.get("status")
        if st in ("completed", "error"):
            return
        time.sleep(poll_interval_seconds)
    return

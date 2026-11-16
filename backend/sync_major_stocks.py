"""Sync routine: ensure each major stock has a report for today."""

import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ai_engine.llm_provider import configured_provider

from config import ALL_ANALYSTS, MAJOR_TICKERS
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
    llm_provider: Optional[str] = None,
    wait_for_completion: bool = True,
    poll_interval_seconds: float = 10.0,
    completion_timeout_seconds: float = 3600.0,
) -> None:
    """
    Start analysis for each ticker in tickers, sequentially. Optionally wait for each to complete.
    Records each new run in analysis_runs (using creator_id or system user).
    """
    if analysts is None:
        analysts = list(ALL_ANALYSTS)
    if creator_id is None:
        creator_id = token_service.get_system_user_id(db)
    if llm_provider is None:
        llm_provider = configured_provider()
    for ticker in tickers:
        analysis_run_id = token_service.record_analysis_run(creator_id, ticker, db)
        returned_run_id, existing = analysis_service.start_analysis(
            ticker=ticker,
            analysis_date=analysis_date,
            analysts=analysts,
            research_depth=research_depth,
            llm_provider=llm_provider,
            progress_callback=None,
            analysis_run_id=analysis_run_id,
        )
        if existing:
            token_service.delete_execution(analysis_run_id, db)
        if wait_for_completion:
            _wait_for_analysis(
                analysis_service,
                returned_run_id,
                poll_interval_seconds=poll_interval_seconds,
                timeout_seconds=completion_timeout_seconds,
            )


def _wait_for_analysis(
    analysis_service: AnalysisService,
    analysis_run_id: int,
    poll_interval_seconds: float = 10.0,
    timeout_seconds: float = 3600.0,
) -> None:
    """Poll analysis status until completed, error, or timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status_info = analysis_service.get_analysis_status(analysis_run_id)
        if status_info is None:
            return
        st = status_info.get("status")
        if st in ("completed", "error"):
            return
        time.sleep(poll_interval_seconds)
    return

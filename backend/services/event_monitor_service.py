"""Event-driven re-analysis.

A report is a point-in-time artifact: once written, nothing revisits it. This service
watches the deterministic event signal already produced by ``processing/event.py`` and
re-runs the analysis when a ticker's signal is both *high* and *much higher than it was
at the last analysis*. Subscribers are then notified through the existing path --
``analysis_service`` already calls ``notify_subscribers_new_report`` on completion, so
there is deliberately no email code here.

The decision is fully deterministic; no LLM is involved.

Baselines are stored as ``Execution`` + ``Report`` rows (``execution_type="event_monitor"``),
the same generic-persistence pattern digests use, so this needs no new table. The latest
baseline row for a ticker is simultaneously the score to compare against and the cooldown
anchor.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.db_models import Execution, Report, Subscription
from services import token_service

logger = logging.getLogger(__name__)

EXECUTION_TYPE = "event_monitor"
BASELINE_REPORT_TYPE = "event_baseline"
RERUN_REPORT_TYPE = "event_rerun"

# Calibrated against the real subscribed universe on 2026-08-13, whose scores were
# 2.25 / 4.50 / 4.50 / 5.00 / 7.50 / 10.25 / 13.50 (median 5.0). ``event_score`` is an
# unbounded *sum* over detected events, so a busy-but-boring ticker outscores an alarming
# one -- IBM's 13.50 was eight events dominated by volatility_compression. A threshold at
# the median would therefore call four of seven tickers "high" on an ordinary day, so the
# bar sits at the top of the observed range instead.
MIN_EVENT_SCORE = 10.0  # "high signal"
# One high-strength new_52w_low is worth 2.5 x 2.0 = 5.0 and a medium price gap 2.0 x 1.5
# = 3.0 (_EVENT_WEIGHT x _STRENGTH_MULTIPLIER in processing/event.py). 4.0 sits above the
# latter so a single mundane event appearing cannot clear the bar on its own.
MIN_SCORE_DELTA = 4.0  # "changed a lot" since the last analysis

# Cost brakes, in the order they bite.
MAX_TICKERS_PER_RUN = 25
COOLDOWN_HOURS = 72
MAX_RERUNS_PER_DAY = 3

RERUN_ANALYSTS = ["market", "social", "fundamentals", "technical", "sec", "valuation"]
RERUN_RESEARCH_DEPTH = 5
RERUN_LLM_PROVIDER = "azure"


def should_rerun(current_score: float, baseline_score: float) -> Tuple[bool, str]:
    """Decide whether a ticker's event signal warrants a fresh analysis.

    Both conditions must hold: the signal is high *now*, and it climbed materially since
    the baseline. A ticker that was already noisy at the last analysis does not re-fire
    just for staying noisy, and a signal that merely decayed never fires.
    """
    if current_score < MIN_EVENT_SCORE:
        return (False, "low_signal")
    if (current_score - baseline_score) < MIN_SCORE_DELTA:
        return (False, "small_delta")
    return (True, "signal_spike")


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def select_monitor_universe(db: Session, *, limit: int = MAX_TICKERS_PER_RUN) -> List[str]:
    """Tickers worth monitoring: someone subscribes and there is a report to invalidate.

    Ordered stalest-analysis-first so that ``limit`` rotates coverage across runs instead
    of repeatedly checking the same head of the list.
    """
    subscribed = {
        (ticker or "").strip().upper()
        for (ticker,) in db.query(Subscription.ticker).distinct().all()
    }
    subscribed.discard("")
    if not subscribed:
        return []

    rows = (
        db.query(Execution.subject_id, func.max(Execution.created_at).label("last_run"))
        .filter(
            Execution.execution_type == "ticker",
            Execution.subject_type == "ticker",
            Execution.status == "completed",
            Execution.subject_id.in_(sorted(subscribed)),
        )
        .group_by(Execution.subject_id)
        .order_by(func.max(Execution.created_at).asc())
        .limit(limit)
        .all()
    )
    return [str(row[0]).upper() for row in rows]


def _latest_analysis_execution_id(db: Session, ticker: str) -> Optional[int]:
    """Id of the most recent completed analysis for a ticker.

    Deliberately queried on the caller's session rather than through
    ``ReportService.get_latest_completed_execution_for_ticker``, which opens its own
    ``SessionLocal`` and so would read a different database under test.
    """
    row = (
        db.query(Execution.id)
        .filter(
            Execution.execution_type == "ticker",
            Execution.subject_type == "ticker",
            Execution.subject_id == ticker.upper(),
            Execution.status == "completed",
        )
        .order_by(Execution.created_at.desc(), Execution.id.desc())
        .first()
    )
    return int(row[0]) if row else None


def load_baseline(db: Session, ticker: str) -> Optional[Dict[str, Any]]:
    """Latest recorded event-score baseline for a ticker, or None if never observed."""
    row = (
        db.query(Execution, Report)
        .join(Report, Report.execution_id == Execution.id)
        .filter(
            Execution.execution_type == EXECUTION_TYPE,
            Execution.subject_type == "ticker",
            Execution.subject_id == ticker.upper(),
            Report.report_type == BASELINE_REPORT_TYPE,
        )
        .order_by(Execution.created_at.desc(), Execution.id.desc())
        .first()
    )
    if row is None:
        return None
    execution, report = row
    try:
        meta = json.loads(report.metadata_json) if report.metadata_json else {}
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "execution_id": execution.id,
        "observed_at": execution.created_at,
        "event_score": _as_float(meta.get("event_score")),
        "analysis_execution_id": meta.get("analysis_execution_id"),
        "dominant_events": meta.get("dominant_events") or [],
    }


def _write_baseline(
    db: Session,
    ticker: str,
    *,
    creator_id: int,
    event_score: float,
    dominant_events: List[str],
    analysis_execution_id: Optional[int],
    baseline_score: Optional[float],
    now: datetime,
    rerun_analysis_id: Optional[int] = None,
) -> int:
    """Persist an observation. Writing this row is what arms the cooldown.

    The ``Execution`` is built inline rather than via ``token_service.record_execution``
    because a monitor observation is already finished when recorded, and that helper
    cannot set ``status``. Everything stays on the caller's session so the write is one
    transaction.
    """
    execution = Execution(
        execution_type=EXECUTION_TYPE,
        subject_type="ticker",
        subject_id=ticker.upper(),
        creator_id=creator_id,
        earned_tokens=0,
        status="completed",
        completed_at=now,
        created_at=now,
    )
    db.add(execution)
    db.flush()

    delta = None if baseline_score is None else round(event_score - baseline_score, 4)
    db.add(
        Report(
            execution_id=execution.id,
            report_type=BASELINE_REPORT_TYPE,
            content="",
            metadata_json=json.dumps(
                {
                    "event_score": event_score,
                    "dominant_events": list(dominant_events or []),
                    "analysis_execution_id": analysis_execution_id,
                    "baseline_score": baseline_score,
                    "delta": delta,
                    "triggered": rerun_analysis_id is not None,
                    "observed_at": now.isoformat(),
                }
            ),
            created_at=now,
        )
    )
    if rerun_analysis_id is not None:
        # A separate report type (rather than a JSON flag) keeps the daily-cap count a
        # plain indexed query instead of a scan over metadata_json.
        db.add(
            Report(
                execution_id=execution.id,
                report_type=RERUN_REPORT_TYPE,
                content="",
                metadata_json=json.dumps(
                    {
                        "analysis_run_id": rerun_analysis_id,
                        "event_score": event_score,
                        "baseline_score": baseline_score,
                        "delta": delta,
                    }
                ),
                created_at=now,
            )
        )
    db.commit()
    return int(execution.id)


def _reruns_today(db: Session, *, now: datetime) -> int:
    """How many re-analyses the monitor has already triggered in the current UTC day."""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(Report.id))
        .join(Execution, Execution.id == Report.execution_id)
        .filter(
            Execution.execution_type == EXECUTION_TYPE,
            Report.report_type == RERUN_REPORT_TYPE,
            Execution.created_at >= day_start,
        )
        .scalar()
    ) or 0


def _start_rerun(
    db: Session,
    ticker: str,
    *,
    creator_id: int,
    analysis_date: str,
    analysis_service: Any = None,
) -> Tuple[Optional[int], bool]:
    """Kick off a system-owned analysis. Mirrors ``sync_major_stocks``."""
    if analysis_service is None:
        import app_services

        analysis_service = app_services.get_analysis_service()

    analysis_run_id = token_service.record_analysis_run(creator_id, ticker, db)
    _returned_run_id, existing = analysis_service.start_analysis(
        ticker=ticker,
        analysis_date=analysis_date,
        analysts=RERUN_ANALYSTS,
        research_depth=RERUN_RESEARCH_DEPTH,
        llm_provider=RERUN_LLM_PROVIDER,
        progress_callback=None,
        analysis_run_id=analysis_run_id,
    )
    if existing:
        # Something else is already analyzing this ticker/date; drop our placeholder run.
        token_service.delete_execution(analysis_run_id, db)
        return (None, True)
    return (analysis_run_id, False)


def check_ticker(
    db: Session,
    ticker: str,
    *,
    allow_rerun: bool = True,
    gateway: Any = None,
    analysis_service: Any = None,
    as_of_date: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evaluate one ticker and, when its signal spiked, start a fresh analysis.

    ``allow_rerun=False`` runs everything except the analysis itself, which makes the
    decision path safe to exercise by hand without spending tokens.
    """
    ticker = ticker.upper()
    now = now or datetime.utcnow()
    as_of_date = as_of_date or now.strftime("%Y-%m-%d")
    result: Dict[str, Any] = {"ticker": ticker, "status": "unknown"}

    baseline = load_baseline(db, ticker)
    if baseline is not None and baseline["observed_at"] is not None:
        if baseline["observed_at"] > now - timedelta(hours=COOLDOWN_HOURS):
            result["status"] = "skipped_cooldown"
            result["last_observed_at"] = baseline["observed_at"].isoformat()
            return result

    analysis_execution_id = _latest_analysis_execution_id(db, ticker)
    if analysis_execution_id is None:
        result["status"] = "skipped_no_analysis"
        return result

    if gateway is None:
        from data_layer import get_data_gateway

        gateway = get_data_gateway()

    from processing import get_ticker_event_summary

    summary = get_ticker_event_summary(gateway, ticker, as_of_date=as_of_date)
    event_score = float(summary.event_score or 0.0)
    dominant_events = list(summary.dominant_events or [])
    result["event_score"] = event_score
    result["dominant_events"] = dominant_events

    creator_id = token_service.get_system_user_id(db)
    baseline_score = baseline["event_score"] if baseline else None

    # Re-anchor whenever we have never seen this ticker, or an analysis has completed
    # since the baseline was taken. This is what makes the comparison "versus the last
    # run" regardless of who triggered that run.
    if baseline_score is None or baseline["analysis_execution_id"] != analysis_execution_id:
        _write_baseline(
            db,
            ticker,
            creator_id=creator_id,
            event_score=event_score,
            dominant_events=dominant_events,
            analysis_execution_id=analysis_execution_id,
            baseline_score=baseline_score,
            now=now,
        )
        result["status"] = "rebaselined"
        result["baseline_score"] = baseline_score
        return result

    result["baseline_score"] = baseline_score
    result["delta"] = round(event_score - baseline_score, 4)

    fire, reason = should_rerun(event_score, baseline_score)
    if not fire:
        result["status"] = f"skipped_{reason}"
        return result

    if not allow_rerun:
        result["status"] = "would_rerun"
        return result

    if _reruns_today(db, now=now) >= MAX_RERUNS_PER_DAY:
        result["status"] = "skipped_daily_cap"
        return result

    analysis_run_id, existing = _start_rerun(
        db,
        ticker,
        creator_id=creator_id,
        analysis_date=as_of_date,
        analysis_service=analysis_service,
    )
    _write_baseline(
        db,
        ticker,
        creator_id=creator_id,
        event_score=event_score,
        dominant_events=dominant_events,
        analysis_execution_id=analysis_execution_id,
        baseline_score=baseline_score,
        now=now,
        rerun_analysis_id=analysis_run_id,
    )
    if existing:
        result["status"] = "skipped_already_running"
        return result

    result["status"] = "rerun_started"
    result["analysis_run_id"] = analysis_run_id
    logger.info(
        "Event monitor re-analysis started ticker=%s event_score=%.2f baseline=%.2f events=%s run_id=%s",
        ticker,
        event_score,
        baseline_score,
        dominant_events,
        analysis_run_id,
    )
    return result


def run_event_monitor(
    db: Session,
    *,
    limit: int = MAX_TICKERS_PER_RUN,
    allow_rerun: bool = True,
    gateway: Any = None,
    analysis_service: Any = None,
    as_of_date: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Check the monitored universe and return a summary suitable for one log line."""
    now = now or datetime.utcnow()
    tickers = select_monitor_universe(db, limit=limit)
    statuses: Dict[str, int] = {}
    reruns: List[str] = []
    errors: List[str] = []

    for ticker in tickers:
        try:
            outcome = check_ticker(
                db,
                ticker,
                allow_rerun=allow_rerun,
                gateway=gateway,
                analysis_service=analysis_service,
                as_of_date=as_of_date,
                now=now,
            )
        except Exception:
            # One unreachable vendor or bad symbol must not abandon the rest of the run.
            logger.exception("Event monitor check failed ticker=%s", ticker)
            db.rollback()
            errors.append(ticker)
            statuses["error"] = statuses.get("error", 0) + 1
            continue
        status = outcome.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if status == "rerun_started":
            reruns.append(ticker)

    return {
        "checked": len(tickers),
        "statuses": statuses,
        "reruns": reruns,
        "errors": errors,
    }

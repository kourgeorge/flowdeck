"""Event-driven re-analysis.

A report is a point-in-time artifact: once written, nothing revisits it. This service
watches the deterministic event signal already produced by ``processing/event.py`` and
re-runs the analysis when a ticker's signal is both *high* and *much higher than it was
at the last analysis*. Subscribers are then notified through the existing path --
``analysis_service`` already calls ``notify_subscribers_new_report`` on completion, so
there is deliberately no email code here.

The decision is fully deterministic; no LLM is involved.

This service keeps no state of its own. The baseline it compares against is the
``event_score`` each analysis records in its own ``trader_investment_plan`` report metadata
(see ``analysis_service._get_analysis_event_meta``), and the cooldown is that analysis's
timestamp. So a ticker analyzed before that recording existed simply has no baseline and is
skipped until its next real analysis -- the repo's "refuse to compute rather than guess"
default, and the reason nothing here needs a backfill.
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

# The report whose metadata carries each analysis's event signal.
SIGNAL_REPORT_TYPE = "trader_investment_plan"

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

# Cost brakes. The cooldown is self-limiting: a re-analysis stamps a fresh event_score and
# resets its own clock, so a firing ticker cannot fire again for COOLDOWN_HOURS.
MAX_TICKERS_PER_RUN = 25
COOLDOWN_HOURS = 72

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


def load_last_analysis(db: Session, ticker: str) -> Optional[Dict[str, Any]]:
    """The ticker's latest completed analysis and the event score it recorded.

    Queried on the caller's session rather than through ``ReportService``, whose helpers each
    open their own ``SessionLocal`` and so would read a different database under test.

    LEFT JOINed so "analyzed but recorded no score" stays distinguishable from "never
    analyzed": the former is a run that predates the recording and gets skipped, not treated
    as a baseline of zero.
    """
    row = (
        db.query(Execution.id, Execution.created_at, Report.metadata_json)
        .outerjoin(
            Report,
            (Report.execution_id == Execution.id)
            & (Report.report_type == SIGNAL_REPORT_TYPE),
        )
        .filter(
            Execution.execution_type == "ticker",
            Execution.subject_type == "ticker",
            Execution.subject_id == ticker.upper(),
            Execution.status == "completed",
        )
        .order_by(Execution.created_at.desc(), Execution.id.desc())
        .first()
    )
    if row is None:
        return None
    execution_id, created_at, metadata_json = row
    try:
        meta = json.loads(metadata_json) if metadata_json else {}
    except (TypeError, ValueError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "execution_id": int(execution_id),
        "analyzed_at": created_at,
        "event_score": _as_float(meta.get("event_score")),
        "dominant_events": meta.get("dominant_events") or [],
    }


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

    last = load_last_analysis(db, ticker)
    if last is None:
        result["status"] = "skipped_no_analysis"
        return result

    # The cooldown is the analysis's own age, so a ticker the monitor just re-analyzed is
    # quiet for COOLDOWN_HOURS without any separate anchor being written.
    if last["analyzed_at"] is not None and last["analyzed_at"] > now - timedelta(hours=COOLDOWN_HOURS):
        result["status"] = "skipped_cooldown"
        result["last_analyzed_at"] = last["analyzed_at"].isoformat()
        return result

    baseline_score = last["event_score"]
    if baseline_score is None:
        # An analysis from before the score was recorded. Guessing a baseline would fabricate
        # a delta, so wait for the next real analysis to supply one.
        result["status"] = "skipped_no_baseline"
        return result

    if gateway is None:
        from data_layer import get_data_gateway

        gateway = get_data_gateway()

    from processing import get_ticker_event_summary

    summary = get_ticker_event_summary(gateway, ticker, as_of_date=as_of_date)
    event_score = float(summary.event_score or 0.0)
    result["event_score"] = event_score
    result["dominant_events"] = list(summary.dominant_events or [])
    result["baseline_score"] = baseline_score
    result["delta"] = round(event_score - baseline_score, 4)

    fire, reason = should_rerun(event_score, baseline_score)
    if not fire:
        result["status"] = f"skipped_{reason}"
        return result

    if not allow_rerun:
        result["status"] = "would_rerun"
        return result

    analysis_run_id, existing = _start_rerun(
        db,
        ticker,
        creator_id=token_service.get_system_user_id(db),
        analysis_date=as_of_date,
        analysis_service=analysis_service,
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
        result["dominant_events"],
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

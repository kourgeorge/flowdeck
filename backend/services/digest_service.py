"""Digest service: generation helpers and history for user briefs."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.db_models import Execution, Report
from services import token_service


logger = logging.getLogger(__name__)


class DigestBriefItem:
    """One brief item (mirrors router DigestBriefItem shape)."""

    def __init__(
        self,
        execution_id: int,
        created_at: str,
        narrative: str,
        what_to_watch: str,
        digest_date: str,
        span_type: str = "daily",
        span_label: str = "Daily",
        priority_tickers: Optional[List[str]] = None,
        important_events: Optional[list[dict]] = None,
        user_note: Optional[str] = None,
        narrative_style: Optional[str] = None,
        user_focus_tickers: Optional[List[str]] = None,
        references: Optional[list] = None,
        raw_metadata: Optional[dict] = None,
    ):
        self.execution_id = execution_id
        self.created_at = created_at
        self.narrative = narrative
        self.what_to_watch = what_to_watch
        self.digest_date = digest_date
        self.span_type = span_type
        self.span_label = span_label
        self.priority_tickers = priority_tickers or []
        self.important_events = important_events or []
        self.user_note = user_note
        self.narrative_style = narrative_style
        self.user_focus_tickers = user_focus_tickers
        self.references = references
        self.raw_metadata = raw_metadata


def _to_utc_iso(value: Optional[datetime]) -> str:
    """Serialize DB datetimes as explicit UTC so clients convert correctly."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize DB datetimes to aware UTC for downstream timezone conversion."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_zone(timezone_name: Optional[str]) -> Optional[ZoneInfo]:
    """Return a validated ZoneInfo or None when the timezone is absent/invalid."""
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return None


def _local_day_for_execution(subject_id: str, created_at: Optional[datetime], timezone_name: Optional[str]) -> Optional[str]:
    """Map a stored daily brief execution to the user's local day when possible."""
    parts = str(subject_id).split(":", 2)
    if len(parts) < 2:
        return None
    slot = parts[1] if len(parts) == 2 else f"{parts[1]}:{parts[2]}"
    if slot.startswith("w:"):
        return slot

    ts = _as_utc(created_at)
    tz = _get_zone(timezone_name)
    if ts is not None and tz is not None:
        return ts.astimezone(tz).date().isoformat()
    return slot


def _utc_bounds_for_local_day(slot: str, timezone_name: Optional[str]) -> Optional[tuple[datetime, datetime]]:
    """Return naive UTC DB bounds for a local calendar day."""
    tz = _get_zone(timezone_name)
    if tz is None:
        return None

    local_start = datetime.strptime(slot, "%Y-%m-%d").replace(tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _build_slot(span_type: str, digest_date: str) -> str:
    """Return slot key used in subject_id."""
    return digest_date if span_type == "daily" else f"w:{digest_date}"


def _parse_span(span_type: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return (span_type, start_date, end_date) for run_digest. Custom not yet supported here."""
    if not span_type or span_type == "daily":
        return "daily", None, None
    if span_type == "weekly":
        return "weekly", None, None
    return "daily", None, None


async def run_and_store_digest(
    db: Session,
    user_id: int,
    *,
    digest_date: str,
    span_type: str,
    max_priority_tickers: int = 5,
    user_note: Optional[str] = None,
    narrative_style: Optional[str] = None,
    user_focus_tickers: Optional[list[str]] = None,
    user_email: Optional[str] = None,
) -> Tuple["DigestResultProtocol", dict, int, str]:
    """
    Shared helper used by both the HTTP API and the scheduler.

    - Deducts tokens and creates an Execution.
    - Runs the digest workflow.
    - Persists the Report with metadata.
    - Sends email notification to user if user_email is provided.
    - Returns (result, metadata, execution_id, slot).
    """
    try:
        from ai_engine.briefing_agent import run_digest  # imported lazily
    except ImportError:
        logger.exception("Digest import failed while loading ai_engine.briefing_agent")
        raise

    slot = _build_slot(span_type, digest_date)
    subject_id = f"{user_id}:{slot}"

    deduct_ok, execution_id = token_service.deduct_for_digest(user_id, subject_id, db)
    if not deduct_ok or execution_id is None:
        raise RuntimeError("Insufficient token balance for User Daily Brief. Please Purchase Tokens.")

    parsed_span_type, start_date, end_date = _parse_span(span_type)

    # Run the heavy work in a background thread.
    import asyncio
    try:
        result = await asyncio.to_thread(
            run_digest,
            user_id=user_id,
            digest_date=digest_date,
            db=db,
            config=None,
            max_priority_tickers=max_priority_tickers,
            user_note=user_note,
            narrative_style=narrative_style,
            user_focus_tickers=user_focus_tickers,
            span_type=parsed_span_type,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:  # pragma: no cover - surface to caller
        logger.exception("Digest generation failed for user_id=%s: %s", user_id, e)
        raise

    metadata: dict = {
        "digest_date": getattr(result, "digest_date", digest_date),
        "span_type": getattr(result, "span_type", parsed_span_type),
        "span_label": getattr(result, "span_label", "Daily"),
        "priority_tickers": getattr(result, "priority_tickers", []),
        "important_events": [
            event.model_dump() if hasattr(event, "model_dump") else event
            for event in (getattr(result, "important_events", None) or [])
        ],
        "what_to_watch": getattr(result, "what_to_watch", ""),
    }
    # Optional per-ticker snapshot for UI: price + span-aware percent change.
    focus_snapshot = getattr(result, "focus_snapshot", None)
    if isinstance(focus_snapshot, dict) and focus_snapshot:
        metadata["focus_snapshot"] = focus_snapshot
    if user_note:
        metadata["user_note"] = user_note
    if narrative_style:
        metadata["narrative_style"] = narrative_style
    if user_focus_tickers:
        metadata["user_focus_tickers"] = user_focus_tickers
    if getattr(result, "references", None):
        metadata["references"] = [
            r.model_dump() if hasattr(r, "model_dump") else r
            for r in (result.references or [])
        ]
    # Optional LLM usage metadata
    for key in ("input_tokens", "output_tokens", "total_tokens", "cost_usd", "models_used"):
        value = getattr(result, key, None)
        if value is not None:
            metadata[key] = value

    from services.report_service import save_report

    save_report(
        execution_id,
        "daily_digest",
        content=getattr(result, "narrative", ""),
        metadata=metadata,
    )

    # Send email notification to user if email is provided (best-effort; do not fail digest)
    if user_email:
        try:
            from services.email_service import send_daily_digest_email_to_user
            send_daily_digest_email_to_user(execution_id, user_email)
            logger.info("Brief email sent to user_id=%s execution_id=%s", user_id, execution_id)
        except Exception as e:
            logger.warning("Failed to send brief email to user_id=%s execution_id=%s: %s", user_id, execution_id, e)

    return result, metadata, execution_id, slot


def get_digest_dates(
    db: Session, user_id: int, days: int, timezone_name: Optional[str] = None
) -> tuple[List[str], dict[str, int]]:
    """
    Return (dates, count_by_date) for the user's digest history in the last `days`.
    dates = list of slot keys (YYYY-MM-DD or w:YYYY-MM-DD) ordered by oldest first,
    so the last slot is the one with the most recent brief (daily or weekly, whichever is later).
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    rows = (
        db.query(Execution.subject_id, Execution.created_at)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == user_id,
            Execution.created_at >= since,
        )
        .all()
    )
    count_by_date: dict[str, int] = {}
    latest_created_by_slot: dict[str, datetime] = {}
    for subject_id, created_at in rows:
        if not subject_id:
            continue
        date_str = _local_day_for_execution(str(subject_id), created_at, timezone_name)
        if date_str:
            count_by_date[date_str] = count_by_date.get(date_str, 0) + 1
            # Keep the latest created_at for this slot (for ordering)
            ts = _as_utc(created_at)
            if ts:
                prev = latest_created_by_slot.get(date_str)
                if prev is None or ts > prev:
                    latest_created_by_slot[date_str] = ts
    # Order slots by latest brief time ascending so the last element is the most recent
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    dates = sorted(
        count_by_date.keys(),
        key=lambda s: (latest_created_by_slot.get(s) or epoch),
    )
    return dates, count_by_date


def _report_to_brief_item(ex: Execution, report: Report, slot: str) -> DigestBriefItem:
    meta: dict = {}
    if report.metadata_json:
        try:
            meta = json.loads(report.metadata_json) or {}
        except Exception:
            meta = {}
    narrative = report.content or ""
    what_to_watch = str(meta.get("what_to_watch") or "")
    digest_date = str(meta.get("digest_date") or slot)
    span_type = str(meta.get("span_type") or "daily")
    span_label = str(meta.get("span_label") or "Daily")
    priority_tickers = meta.get("priority_tickers") or []
    if not isinstance(priority_tickers, list):
        priority_tickers = []
    important_events = meta.get("important_events") or []
    if not isinstance(important_events, list):
        important_events = []
    user_note = meta.get("user_note")
    narrative_style = meta.get("narrative_style")
    user_focus_tickers = meta.get("user_focus_tickers") or None
    if user_focus_tickers is not None and not isinstance(user_focus_tickers, list):
        user_focus_tickers = None
    refs = meta.get("references")
    if refs is not None and not isinstance(refs, list):
        refs = None
    created_at = _to_utc_iso(ex.created_at)
    return DigestBriefItem(
        execution_id=ex.id,
        created_at=created_at,
        narrative=narrative,
        what_to_watch=what_to_watch,
        digest_date=digest_date,
        span_type=span_type,
        span_label=span_label,
        priority_tickers=[str(t) for t in priority_tickers],
        important_events=[event for event in important_events if isinstance(event, dict)],
        user_note=str(user_note) if user_note is not None else None,
        narrative_style=str(narrative_style) if narrative_style is not None else None,
        user_focus_tickers=[str(t) for t in (user_focus_tickers or [])] or None,
        references=refs,
        raw_metadata=meta or None,
    )


def get_digests_for_date(
    db: Session, user_id: int, slot: str, timezone_name: Optional[str] = None
) -> List[DigestBriefItem]:
    """
    Return all stored briefs for the given slot for the user, newest first.
    slot: YYYY-MM-DD (daily) or w:YYYY-MM-DD (weekly).
    """
    query = (
        db.query(Execution)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == user_id,
        )
        .order_by(Execution.created_at.desc())
    )

    if slot.startswith("w:"):
        subject_id = f"{user_id}:{slot}"
        executions = query.filter(Execution.subject_id == subject_id).all()
    else:
        bounds = _utc_bounds_for_local_day(slot, timezone_name)
        if bounds is not None:
            start_utc, end_utc = bounds
            executions = (
                query
                .filter(
                    Execution.created_at >= start_utc,
                    Execution.created_at < end_utc,
                    ~Execution.subject_id.like(f"{user_id}:w:%"),
                )
                .all()
            )
        else:
            subject_id = f"{user_id}:{slot}"
            executions = query.filter(Execution.subject_id == subject_id).all()

    briefs: List[DigestBriefItem] = []
    for ex in executions:
        report = (
            db.query(Report)
            .filter(
                Report.execution_id == ex.id,
                Report.report_type == "daily_digest",
            )
            .first()
        )
        if report:
            briefs.append(_report_to_brief_item(ex, report, slot))
    return briefs


def delete_brief(db: Session, user_id: int, execution_id: int) -> bool:
    """
    Delete a daily_digest brief (Execution and its Reports; Reports cascade).
    Returns True if deleted, False if not found or not owned by user.
    """
    ex = (
        db.query(Execution)
        .filter(
            Execution.id == execution_id,
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == user_id,
        )
        .first()
    )
    if not ex:
        return False
    db.delete(ex)
    db.commit()
    return True

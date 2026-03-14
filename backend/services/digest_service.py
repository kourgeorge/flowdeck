"""Digest history: dates and briefs for a user. Read-only DB access for digest API."""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from models.db_models import Execution, Report


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
        self.user_note = user_note
        self.narrative_style = narrative_style
        self.user_focus_tickers = user_focus_tickers
        self.references = references
        self.raw_metadata = raw_metadata


def get_digest_dates(
    db: Session, user_id: int, days: int
) -> tuple[List[str], dict[str, int]]:
    """
    Return (dates, count_by_date) for the user's digest history in the last `days`.
    dates = sorted list of slot keys (YYYY-MM-DD or w:YYYY-MM-DD).
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    rows = (
        db.query(Execution.subject_id)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.creator_id == user_id,
            Execution.created_at >= since,
        )
        .all()
    )
    count_by_date: dict[str, int] = {}
    for (subject_id,) in rows:
        if not subject_id:
            continue
        parts = str(subject_id).split(":", 2)
        if len(parts) < 2:
            continue
        date_str = parts[1] if len(parts) == 2 else f"{parts[1]}:{parts[2]}"
        if date_str:
            count_by_date[date_str] = count_by_date.get(date_str, 0) + 1
    dates = sorted(count_by_date.keys())
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
    user_note = meta.get("user_note")
    narrative_style = meta.get("narrative_style")
    user_focus_tickers = meta.get("user_focus_tickers") or None
    if user_focus_tickers is not None and not isinstance(user_focus_tickers, list):
        user_focus_tickers = None
    refs = meta.get("references")
    if refs is not None and not isinstance(refs, list):
        refs = None
    created_at = ex.created_at.isoformat() if ex.created_at else ""
    return DigestBriefItem(
        execution_id=ex.id,
        created_at=created_at,
        narrative=narrative,
        what_to_watch=what_to_watch,
        digest_date=digest_date,
        span_type=span_type,
        span_label=span_label,
        priority_tickers=[str(t) for t in priority_tickers],
        user_note=str(user_note) if user_note is not None else None,
        narrative_style=str(narrative_style) if narrative_style is not None else None,
        user_focus_tickers=[str(t) for t in (user_focus_tickers or [])] or None,
        references=refs,
        raw_metadata=meta or None,
    )


def get_digests_for_date(
    db: Session, user_id: int, slot: str
) -> List[DigestBriefItem]:
    """
    Return all stored briefs for the given slot for the user, newest first.
    slot: YYYY-MM-DD (daily) or w:YYYY-MM-DD (weekly).
    """
    subject_id = f"{user_id}:{slot}"
    executions = (
        db.query(Execution)
        .filter(
            Execution.execution_type == "daily_digest",
            Execution.subject_type == "user_date",
            Execution.subject_id == subject_id,
            Execution.creator_id == user_id,
        )
        .order_by(Execution.created_at.desc())
        .all()
    )
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

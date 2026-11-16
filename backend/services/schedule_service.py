"""User schedule service: generic per-user job scheduling configuration.

This service manages `UserSchedule` rows, which are used by the digest scheduler
and can be extended later for other schedule types (alerts, reminders, etc.).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from models.db_models import UserSchedule


DIGEST_DAILY_TYPE = "daily_digest"
DIGEST_WEEKLY_TYPE = "weekly_digest"


MAX_TIMEZONE_LENGTH = 64
INVALID_TIMEZONE_MESSAGE = "Choose a valid IANA timezone, such as America/New_York."


def validate_timezone_name(tz_name: str) -> None:
    """Raise ValueError unless tz_name is a zone zoneinfo can load.

    The scheduler silently falls back to the default zone for names it cannot
    load (e.g. "Athens", "EST5"), so a bad value saved here means emails quietly
    go out at the wrong hour. Rejecting it on save is the only visible signal.

    Folder names in the tz database ("America", "Etc") make ZoneInfo raise
    IsADirectoryError, and very long keys raise OSError (filename too long), so
    OSError is caught too; otherwise those reached the route as a 500. The
    length cap matches the String(64) UserSchedule.timezone column and is
    checked here (not in the pydantic model) so an over-long name gets the
    same 400 message as any other bad name instead of a 422.
    """
    if not isinstance(tz_name, str) or len(tz_name) > MAX_TIMEZONE_LENGTH:
        raise ValueError(INVALID_TIMEZONE_MESSAGE)
    try:
        ZoneInfo(tz_name)
    except (ValueError, ZoneInfoNotFoundError, OSError) as exc:
        raise ValueError(INVALID_TIMEZONE_MESSAGE) from exc


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_user_schedule_by_type(db: Session, user_id: int, schedule_type: str) -> Optional[UserSchedule]:
    """Return a single schedule for a user and type, if present."""
    return (
        db.query(UserSchedule)
        .filter(
            UserSchedule.user_id == user_id,
            UserSchedule.schedule_type == schedule_type,
        )
        .first()
    )


def upsert_user_schedule(
    db: Session,
    user_id: int,
    schedule_type: str,
    *,
    enabled: Optional[bool] = None,
    cron_expression: Optional[str] = None,
    timezone_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UserSchedule:
    """
    Create or update a schedule for the given user and type.

    The API is intentionally generic; callers (e.g. digest routes) decide how fields map
    to their specific schedule semantics.
    """
    schedule = get_user_schedule_by_type(db, user_id, schedule_type)
    is_new = schedule is None
    if schedule is None:
        schedule = UserSchedule(
            user_id=user_id,
            schedule_type=schedule_type,
        )
        db.add(schedule)

    if enabled is not None:
        schedule.enabled = enabled
    if cron_expression is not None:
        schedule.cron_expression = cron_expression
    schedule.timezone = timezone_name
    if metadata is not None:
        schedule.metadata_json = json.dumps(metadata)
    if is_new:
        schedule.created_at = _now_utc()
    schedule.updated_at = _now_utc()
    db.commit()
    db.refresh(schedule)
    return schedule


def decode_metadata(schedule: UserSchedule) -> Dict[str, Any]:
    """Decode schedule.metadata_json to a dict (empty dict on failure)."""
    if not schedule.metadata_json:
        return {}
    try:
        data = json.loads(schedule.metadata_json)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def get_digest_schedules_for_user(
    db: Session,
    user_id: int,
) -> Tuple[Optional[UserSchedule], Optional[UserSchedule]]:
    """
    Convenience helper: return (daily_schedule, weekly_schedule) for a user.
    """
    daily = get_user_schedule_by_type(db, user_id, DIGEST_DAILY_TYPE)
    weekly = get_user_schedule_by_type(db, user_id, DIGEST_WEEKLY_TYPE)
    return daily, weekly


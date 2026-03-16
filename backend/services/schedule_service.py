"""User schedule service: generic per-user job scheduling configuration.

This service manages `UserSchedule` rows, which are used by the digest scheduler
and can be extended later for other schedule types (alerts, reminders, etc.).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models.db_models import UserSchedule


DIGEST_DAILY_TYPE = "daily_digest"
DIGEST_WEEKLY_TYPE = "weekly_digest"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_user_schedules(db: Session, user_id: int) -> List[UserSchedule]:
    """Return all schedules for a user."""
    return (
        db.query(UserSchedule)
        .filter(UserSchedule.user_id == user_id)
        .order_by(UserSchedule.created_at.asc())
        .all()
    )


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
    time_window: Optional[str] = None,
    time_of_day: Optional[str] = None,
    timezone_name: Optional[str] = None,
    weekday: Optional[int] = None,
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
    # Only one of time_of_day / time_window is expected to be actively used, but we don't enforce here.
    schedule.time_window = time_window
    schedule.time_of_day = time_of_day
    schedule.timezone = timezone_name
    schedule.weekday = weekday
    if metadata is not None:
        schedule.metadata_json = json.dumps(metadata)
    if is_new:
        schedule.created_at = _now_utc()
    schedule.updated_at = _now_utc()
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_user_schedule(db: Session, user_id: int, schedule_id: int) -> bool:
    """Delete a schedule if it belongs to the user. Returns True if deleted."""
    schedule = (
        db.query(UserSchedule)
        .filter(
            UserSchedule.id == schedule_id,
            UserSchedule.user_id == user_id,
        )
        .first()
    )
    if not schedule:
        return False
    db.delete(schedule)
    db.commit()
    return True


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


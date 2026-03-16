"""General scheduler utilities for time-based jobs.

Currently used to run and email User Daily Briefs (daily/weekly digests)
based on `UserSchedule`, but designed so additional schedule types can be
handled in the same loop in the future.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from zoneinfo import ZoneInfo

from database import SessionLocal
from models.db_models import User, UserSchedule
from services.digest_service import run_and_store_digest
from services.email_service import send_daily_digest_email_to_user


logger = logging.getLogger(__name__)


def _get_default_timezone() -> str:
    return os.environ.get("DIGEST_DEFAULT_TIMEZONE", "UTC")


def _parse_time_of_day(value: Optional[str]) -> Optional[time]:
    if not value:
        return None
    try:
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour=hour, minute=minute)
    except Exception:
        return None


def _is_within_window(now_local: datetime, schedule: UserSchedule) -> bool:
    """Check if now_local lies within the schedule's configured time-of-day window."""
    t_exact = _parse_time_of_day(schedule.time_of_day)
    if t_exact is None:
        # No specific time configured: allow anytime during the day.
        return True
    # Allow a small ±10 minute tolerance so a 10–15 minute scheduler interval can catch it.
    window_start = datetime.combine(now_local.date(), t_exact, tzinfo=now_local.tzinfo) - timedelta(minutes=10)
    window_end = datetime.combine(now_local.date(), t_exact, tzinfo=now_local.tzinfo) + timedelta(minutes=10)
    return window_start <= now_local <= window_end


def _has_run_today(schedule: UserSchedule, now_local: datetime) -> bool:
    if not schedule.last_executed_at:
        return False
    last_local = schedule.last_executed_at.astimezone(now_local.tzinfo)
    return last_local.date() == now_local.date()


def _has_run_this_week(schedule: UserSchedule, now_local: datetime) -> bool:
    if not schedule.last_executed_at:
        return False
    last_local = schedule.last_executed_at.astimezone(now_local.tzinfo)
    # Same ISO week and year considered "this week".
    return (last_local.isocalendar()[:2] == now_local.isocalendar()[:2])


def _should_run_daily(now_utc: datetime, schedule: UserSchedule, tz: ZoneInfo) -> bool:
    now_local = now_utc.astimezone(tz)
    if _has_run_today(schedule, now_local):
        return False
    if not _is_within_window(now_local, schedule):
        return False
    return True


def _should_run_weekly(now_utc: datetime, schedule: UserSchedule, tz: ZoneInfo) -> bool:
    now_local = now_utc.astimezone(tz)
    weekday = schedule.weekday
    if weekday is not None and now_local.weekday() != int(weekday):
        return False
    if _has_run_this_week(schedule, now_local):
        return False
    if not _is_within_window(now_local, schedule):
        return False
    return True


async def run_scheduled_jobs() -> None:
    """
    Entry point for APScheduler.

    - Finds active schedules (currently daily/weekly digests).
    - For each matching schedule, runs the job (digest generation) and sends email.
    - Updates last_executed_at for successfully executed schedules.
    """
    now_utc = datetime.now(timezone.utc)
    default_tz = ZoneInfo(_get_default_timezone())

    db = SessionLocal()
    try:
        schedules = (
            db.query(UserSchedule)
            .join(User, User.id == UserSchedule.user_id)
            .filter(
                UserSchedule.enabled.is_(True),
                UserSchedule.schedule_type.in_(["daily_digest", "weekly_digest"]),
                User.email.isnot(None),
            )
            .all()
        )

        for schedule in schedules:
            try:
                tz_name = schedule.timezone or _get_default_timezone()
                try:
                    tz = ZoneInfo(tz_name)
                except Exception:
                    tz = default_tz

                if schedule.schedule_type == "daily_digest":
                    if not _should_run_daily(now_utc, schedule, tz):
                        continue
                    span_type = "daily"
                else:
                    if not _should_run_weekly(now_utc, schedule, tz):
                        continue
                    span_type = "weekly"

                user = db.query(User).filter(User.id == schedule.user_id).first()
                if not user or not user.email:
                    continue

                now_local = now_utc.astimezone(tz)
                digest_date = now_local.date().isoformat()

                # Decode any digest-specific metadata from the schedule.
                import json

                metadata = {}
                if schedule.metadata_json:
                    try:
                        metadata = json.loads(schedule.metadata_json) or {}
                    except Exception:
                        metadata = {}

                user_note = metadata.get("user_note")
                narrative_style = metadata.get("narrative_style")
                user_focus_tickers = metadata.get("user_focus_tickers") or None
                if user_focus_tickers is not None and not isinstance(user_focus_tickers, list):
                    user_focus_tickers = None

                result, _meta, execution_id, _slot = await run_and_store_digest(
                    db,
                    user.id,
                    digest_date=digest_date,
                    span_type=span_type,
                    user_note=user_note,
                    narrative_style=narrative_style,
                    user_focus_tickers=user_focus_tickers,
                )

                if execution_id:
                    ok = send_daily_digest_email_to_user(execution_id, user.email)
                    if ok:
                        schedule.last_executed_at = now_utc
                        db.commit()
                        logger.info(
                            "Scheduled digest sent: user_id=%s execution_id=%s span=%s",
                            user.id,
                            execution_id,
                            span_type,
                        )
                    else:
                        logger.warning(
                            "Scheduled digest email failed to send: user_id=%s execution_id=%s",
                            user.id,
                            execution_id,
                        )
            except Exception:
                logger.exception("Scheduled digest run failed for schedule_id=%s", schedule.id)
                db.rollback()
    finally:
        db.close()


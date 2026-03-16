"""General scheduler utilities for time-based jobs.

Currently used to run and email User Daily Briefs (daily/weekly digests)
based on `UserSchedule`, but designed so additional schedule types can be
handled in the same loop in the future.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from zoneinfo import ZoneInfo

from database import SessionLocal
from models.db_models import User, UserSchedule
from services.digest_service import run_and_store_digest
from services.email_service import send_daily_digest_email_to_user


logger = logging.getLogger(__name__)


def _get_default_timezone() -> str:
    return os.environ.get("DIGEST_DEFAULT_TIMEZONE", "UTC")


def _cron_field_matches(value: int, field: str) -> bool:
    """
    Minimal cron field matcher.

    Supports:
    - "*" (any)
    - "N" (single integer)
    - "a,b,c" (list of integers)
    """
    field = (field or "").strip()
    if field == "*" or not field:
        return True
    parts = field.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            if value == int(part):
                return True
        except ValueError:
            continue
    return False


def _cron_matches(now_local: datetime, expr: str) -> bool:
    """
    Check whether a 5-field cron expression matches the given local datetime
    at minute resolution: "min hour day month weekday".
    """
    expr = (expr or "").strip()
    fields = expr.split()
    if len(fields) != 5:
        return False
    minute_f, hour_f, dom_f, month_f, dow_f = fields

    minute = now_local.minute
    hour = now_local.hour
    day = now_local.day
    month = now_local.month
    # Python: Monday=0..Sunday=6, cron: Sunday=0 or 7. We accept 0-6 here for simplicity.
    dow = now_local.weekday()

    return (
        _cron_field_matches(minute, minute_f)
        and _cron_field_matches(hour, hour_f)
        and _cron_field_matches(day, dom_f)
        and _cron_field_matches(month, month_f)
        and _cron_field_matches(dow, dow_f)
    )


def _should_run_now(now_utc: datetime, schedule: UserSchedule, default_tz: ZoneInfo) -> bool:
    """Return True if the cron expression matches now and we haven't run in this minute yet."""
    expr = (schedule.cron_expression or "").strip()
    if not expr:
        return False

    tz_name = schedule.timezone or _get_default_timezone()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = default_tz

    now_local = now_utc.astimezone(tz).replace(second=0, microsecond=0)

    if not _cron_matches(now_local, expr):
        return False

    if schedule.last_executed_at:
        last_local = schedule.last_executed_at.astimezone(tz).replace(second=0, microsecond=0)
        if last_local == now_local:
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
    default_tz_name = _get_default_timezone()
    default_tz = ZoneInfo(default_tz_name)

    logger.info(
        "Scheduled jobs tick at %s (default_tz=%s)",
        now_utc.isoformat(),
        default_tz_name,
    )

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

        logger.info(
            "Found %d active user schedules for digest processing",
            len(schedules),
        )

        processed_count = 0

        for schedule in schedules:
            try:
                if not _should_run_now(now_utc, schedule, default_tz):
                    continue

                tz_name = schedule.timezone or _get_default_timezone()
                try:
                    tz = ZoneInfo(tz_name)
                except Exception:
                    tz = default_tz

                span_type = "daily" if schedule.schedule_type == "daily_digest" else "weekly"

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
                        processed_count += 1
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

    logger.info(
        "Scheduled jobs tick complete at %s; digests sent: %d",
        datetime.now(timezone.utc).isoformat(),
        processed_count,
    )


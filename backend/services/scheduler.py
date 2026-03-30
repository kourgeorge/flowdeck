"""General scheduler utilities for time-based jobs.

Currently used to run and email User Daily Briefs (daily/weekly digests)
based on `UserSchedule`, but designed so additional schedule types can be
handled in the same loop in the future.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
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
    """
    Return True if this schedule should run on this tick.

    Semantics:
    - Daily digests: run at/after the configured local time once per local day.
    - Weekly digests: run at/after the configured local weekday+time once per local ISO week.

    This is more tolerant than strict cron matching, so it still works even when
    the APScheduler interval does not land exactly on the scheduled minute.
    """
    expr = (schedule.cron_expression or "").strip()
    if not expr:
        return False

    fields = expr.split()
    if len(fields) != 5:
        return False

    minute_f, hour_f, _dom_f, _month_f, dow_f = fields
    try:
        scheduled_minute = int(minute_f)
        scheduled_hour = int(hour_f)
    except ValueError:
        return False

    tz_name = schedule.timezone or _get_default_timezone()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = default_tz

    now_local = now_utc.astimezone(tz).replace(second=0, microsecond=0)

    # Compute local datetime for the scheduled time in the current period (day or week).
    if schedule.schedule_type == "daily_digest":
        scheduled_dt = now_local.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)

        # If we've already run once today in local time, skip.
        if schedule.last_executed_at:
            last_local = schedule.last_executed_at.astimezone(tz)
            if last_local.date() == now_local.date():
                return False

        # Run if we've reached or passed the scheduled time today.
        return now_local >= scheduled_dt

    if schedule.schedule_type == "weekly_digest":
        # Determine scheduled weekday from cron (0-6, matching Python's Monday=0..Sunday=6).
        dow_f = dow_f.strip()
        try:
            scheduled_weekday = int(dow_f)
        except ValueError:
            # Fallback: if invalid weekday, do not run.
            return False

        # Local ISO week/year for "once per week" semantics.
        iso_year, iso_week, _iso_dow = now_local.isocalendar()

        if schedule.last_executed_at:
            last_local = schedule.last_executed_at.astimezone(tz)
            last_year, last_week, _ = last_local.isocalendar()
            # Already ran in this ISO week.
            if (last_year, last_week) == (iso_year, iso_week):
                return False

        # Compute the scheduled date for this week.
        # now_local.weekday(): 0=Mon..6=Sun
        today_weekday = now_local.weekday()
        # Start of this week (Monday).
        start_of_week = now_local.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        ) - timedelta(days=today_weekday)
        scheduled_date = start_of_week + timedelta(days=scheduled_weekday)
        scheduled_dt = scheduled_date.replace(
            hour=scheduled_hour,
            minute=scheduled_minute,
            second=0,
            microsecond=0,
        )

        # Run if we've reached or passed the scheduled datetime this week.
        return now_local >= scheduled_dt

    # Unknown schedule_type – be conservative and do not run.
    return False


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

                # Mark as executed IMMEDIATELY to prevent duplicate runs on the same tick
                # or if the process crashes/fails. We update this timestamp before attempting
                # the digest generation to ensure we don't retry on every scheduler tick.
                schedule.last_executed_at = now_utc
                db.commit()

                tz_name = schedule.timezone or _get_default_timezone()
                try:
                    tz = ZoneInfo(tz_name)
                except Exception:
                    tz = default_tz

                span_type = "daily" if schedule.schedule_type == "daily_digest" else "weekly"

                user = db.query(User).filter(User.id == schedule.user_id).first()
                if not user or not user.email:
                    logger.warning(
                        "Skipping schedule_id=%s: user not found or no email",
                        schedule.id,
                    )
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

                logger.info(
                    "Starting scheduled digest: user_id=%s schedule_id=%s span=%s date=%s",
                    user.id,
                    schedule.id,
                    span_type,
                    digest_date,
                )

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
                        processed_count += 1
                        logger.info(
                            "Scheduled digest sent successfully: user_id=%s execution_id=%s span=%s",
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
                else:
                    logger.warning(
                        "Scheduled digest generation returned no execution_id: user_id=%s",
                        user.id,
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


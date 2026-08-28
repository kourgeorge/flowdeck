"""User schedule API for User Daily Brief (digest) emails.

This exposes a simple per-user configuration for:
- Daily brief email
- Weekly brief email

Backed by `UserSchedule` rows and the generic scheduler loop in `services.scheduler`.
"""

from __future__ import annotations

from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from services.schedule_service import (
    DIGEST_DAILY_TYPE,
    DIGEST_WEEKLY_TYPE,
    decode_metadata,
    get_digest_schedules_for_user,
    upsert_user_schedule,
)


router = APIRouter(prefix="/api", tags=["Digests"])


class DigestScheduleMetadata(BaseModel):
    """Schedule-specific options used by the digest scheduler."""

    user_note: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional note that will be passed to each scheduled brief run.",
    )
    narrative_style: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional narrative style hint, e.g. 'concise', 'professional', 'technical'.",
    )
    user_focus_tickers: Optional[list[str]] = Field(
        default=None,
        description="Optional explicit list of portfolio tickers to emphasize in each scheduled brief.",
    )


class DigestScheduleOut(BaseModel):
    """Client-facing representation of a digest schedule."""

    id: int
    schedule_type: Literal["daily_digest", "weekly_digest"]
    enabled: bool
    timezone: Optional[str]
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    # Python weekday, Monday=0..Sunday=6. Only used for weekly schedules.
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    metadata: DigestScheduleMetadata
    last_executed_at: Optional[str] = None


class DigestSchedulesResponse(BaseModel):
    daily: Optional[DigestScheduleOut] = None
    weekly: Optional[DigestScheduleOut] = None


class DigestScheduleUpdateRequest(BaseModel):
    enabled: bool = Field(
        default=True,
        description="Enable or disable this schedule. Disabled schedules are ignored by the scheduler.",
    )
    hour: int = Field(ge=0, le=23, description="Local hour (0-23) for the brief to run.")
    minute: int = Field(ge=0, le=59, description="Local minute (0-59) for the brief to run.")
    # For weekly schedules only; ignored for daily.
    day_of_week: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Local weekday (0=Monday..6=Sunday). Required for weekly schedules.",
    )
    timezone: Optional[str] = Field(
        default=None,
        max_length=64,
        description="IANA timezone identifier, e.g. 'Europe/Athens'. When null, backend default is used.",
    )
    metadata: Optional[DigestScheduleMetadata] = None


def _to_digest_schedule_out(
    *,
    schedule,
    schedule_type: Literal["daily_digest", "weekly_digest"],
) -> Optional[DigestScheduleOut]:
    if schedule is None:
        return None

    expr = (schedule.cron_expression or "").strip()
    parts = expr.split()
    if len(parts) != 5:
        raise HTTPException(status_code=500, detail="Invalid cron expression stored for schedule.")
    minute_str, hour_str, _dom, _month, dow_str = parts
    try:
        minute = int(minute_str)
        hour = int(hour_str)
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid cron time fields stored for schedule.")

    day_of_week: Optional[int] = None
    if schedule_type == DIGEST_WEEKLY_TYPE:
        # We expect a single integer 0-6 for weekly schedules.
        dow_str = dow_str.strip()
        if dow_str == "*" or dow_str == "":
            raise HTTPException(status_code=500, detail="Weekly schedule missing weekday in cron expression.")
        try:
            day_of_week = int(dow_str)
        except ValueError:
            raise HTTPException(status_code=500, detail="Invalid weekday field stored for weekly schedule.")

    meta_dict = decode_metadata(schedule)
    metadata = DigestScheduleMetadata(
        user_note=meta_dict.get("user_note"),
        narrative_style=meta_dict.get("narrative_style"),
        user_focus_tickers=meta_dict.get("user_focus_tickers"),
    )

    return DigestScheduleOut(
        id=schedule.id,
        schedule_type=schedule_type,
        enabled=bool(schedule.enabled),
        timezone=schedule.timezone,
        hour=hour,
        minute=minute,
        day_of_week=day_of_week,
        metadata=metadata,
        last_executed_at=schedule.last_executed_at.isoformat() if schedule.last_executed_at else None,
    )


@router.get("/digest/schedules", response_model=DigestSchedulesResponse)
def get_my_digest_schedules(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return daily/weekly digest email schedules for the current user (if any)."""
    daily, weekly = get_digest_schedules_for_user(db, current_user.id)
    daily_out = _to_digest_schedule_out(schedule=daily, schedule_type=DIGEST_DAILY_TYPE) if daily else None
    weekly_out = _to_digest_schedule_out(schedule=weekly, schedule_type=DIGEST_WEEKLY_TYPE) if weekly else None
    return DigestSchedulesResponse(daily=daily_out, weekly=weekly_out)


@router.put(
    "/digest/schedules/{schedule_type}",
    response_model=DigestScheduleOut,
)
def upsert_my_digest_schedule(
    payload: DigestScheduleUpdateRequest,
    schedule_type: Literal["daily_digest", "weekly_digest"] = Path(..., description="Schedule type to configure."),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create or update a digest schedule (daily or weekly) for the current user.

    The scheduler will generate a brief at the given local time and email it to the
    user's account email whenever the schedule matches.
    """
    if schedule_type == DIGEST_WEEKLY_TYPE and payload.day_of_week is None:
        raise HTTPException(status_code=400, detail="day_of_week is required for weekly schedules.")

    minute = payload.minute
    hour = payload.hour
    if schedule_type == DIGEST_DAILY_TYPE:
        cron_expression = f"{minute} {hour} * * *"
    else:
        # Weekly: restrict to a single weekday.
        cron_expression = f"{minute} {hour} * * {payload.day_of_week}"

    metadata_dict = None
    if payload.metadata is not None:
        metadata_dict = payload.metadata.model_dump(exclude_none=True)

    schedule = upsert_user_schedule(
        db,
        current_user.id,
        schedule_type=schedule_type,
        enabled=payload.enabled,
        cron_expression=cron_expression,
        timezone_name=payload.timezone,
        metadata=metadata_dict,
    )

    return _to_digest_schedule_out(schedule=schedule, schedule_type=schedule_type)


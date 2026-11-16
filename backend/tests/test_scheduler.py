import time
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from services.scheduler import _should_run_now

UTC = ZoneInfo("UTC")


def _schedule(cron, schedule_type="daily_digest", last=None, tz="UTC"):
    return SimpleNamespace(
        cron_expression=cron,
        schedule_type=schedule_type,
        timezone=tz,
        last_executed_at=last,
    )


@pytest.fixture
def athens_host_tz(monkeypatch):
    # Pretend the server runs in Europe/Athens, then put the real host TZ back
    # so the change cannot leak into other tests.
    monkeypatch.setenv("TZ", "Europe/Athens")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_daily_runs_at_scheduled_time_not_before():
    s = _schedule("0 8 * * *")
    assert _should_run_now(datetime(2026, 11, 17, 7, 59, tzinfo=timezone.utc), s, UTC) is False
    assert _should_run_now(datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc), s, UTC) is True


def test_daily_naive_last_run_is_read_as_utc_on_non_utc_host(athens_host_tz):
    # Stored naive by SQLite: 00:30 UTC on Nov 17. Read as Athens local time
    # it would become Nov 16 22:30 UTC and the digest would run again.
    s = _schedule("0 8 * * *", last=datetime(2026, 11, 17, 0, 30))
    now = datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)
    assert _should_run_now(now, s, UTC) is False


def test_weekly_runs_once_per_iso_week():
    # Code numbers weekdays Python-style, so "0" means Monday. 2026-11-16 is a Monday.
    now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
    cron = "0 18 * * 0"

    assert _should_run_now(now, _schedule(cron, "weekly_digest"), UTC) is True
    assert _should_run_now(
        datetime(2026, 11, 16, 17, 59, tzinfo=timezone.utc), _schedule(cron, "weekly_digest"), UTC
    ) is False
    # Already ran earlier this ISO week (naive UTC, as stored).
    assert _should_run_now(
        now, _schedule(cron, "weekly_digest", last=datetime(2026, 11, 16, 0, 5)), UTC
    ) is False
    # Last ran the previous ISO week.
    assert _should_run_now(
        now, _schedule(cron, "weekly_digest", last=datetime(2026, 11, 15, 23, 0)), UTC
    ) is True


def test_bad_cron_does_not_run():
    now = datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc)
    assert _should_run_now(now, _schedule("bad"), UTC) is False
    assert _should_run_now(now, _schedule("0 8 * * *", "weekly_digest"), UTC) is False

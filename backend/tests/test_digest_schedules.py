"""Digest schedule route: invalid timezones are rejected instead of silently becoming UTC."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import Base, get_db
from models.db_models import User, UserSchedule
from routers.schedule import router


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(email="digest@example.com", name="Digest User")
    db.add(user)
    db.commit()
    db.refresh(user)

    app = FastAPI()
    app.include_router(router)

    def _db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, db, user
    db.close()
    engine.dispose()


def test_invalid_timezone_is_rejected_and_nothing_saved(ctx):
    client, db, user = ctx
    resp = client.put(
        "/api/digest/schedules/daily_digest",
        json={"hour": 8, "minute": 0, "timezone": "Mars/Olympus"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Choose a valid IANA timezone, such as America/New_York."
    assert db.query(UserSchedule).filter(UserSchedule.user_id == user.id).count() == 0


def test_valid_timezone_is_saved(ctx):
    client, _db, _user = ctx
    resp = client.put(
        "/api/digest/schedules/daily_digest",
        json={"hour": 8, "minute": 0, "timezone": "Europe/Athens"},
    )
    assert resp.status_code == 200

    daily = client.get("/api/digest/schedules").json()["daily"]
    assert daily["timezone"] == "Europe/Athens"
    assert daily["hour"] == 8


def test_weekly_without_day_of_week_is_rejected(ctx):
    client, db, user = ctx
    resp = client.put(
        "/api/digest/schedules/weekly_digest",
        json={"hour": 8, "minute": 0, "timezone": "Europe/Athens"},
    )
    assert resp.status_code == 400
    assert db.query(UserSchedule).filter(UserSchedule.user_id == user.id).count() == 0


@pytest.mark.parametrize(
    "tz_name",
    # "America"/"Etc" are folders in the tz database and made ZoneInfo raise
    # IsADirectoryError (a 500 before); the long name raises OSError.
    ["America", "Etc", "", "../etc/passwd", "A" * 300],
)
def test_digest_rejects_bad_timezone_names_with_400(ctx, tz_name):
    client, db, user = ctx
    resp = client.put(
        "/api/digest/schedules/daily_digest",
        json={"hour": 8, "minute": 0, "timezone": tz_name},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Choose a valid IANA timezone, such as America/New_York."
    assert db.query(UserSchedule).filter(UserSchedule.user_id == user.id).count() == 0


def test_watchlist_rejects_timezone_folder_name_with_400(ctx):
    client, _db, _user = ctx
    resp = client.put("/api/watchlist/notifications", json={"enabled": True, "timezone": "America"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Choose a valid IANA timezone, such as America/New_York."


def test_digest_still_accepts_europe_athens(ctx):
    client, _db, _user = ctx
    resp = client.put(
        "/api/digest/schedules/daily_digest",
        json={"hour": 8, "minute": 0, "timezone": "Europe/Athens"},
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Europe/Athens"

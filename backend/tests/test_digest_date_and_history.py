"""Digest: bad dates are refused before charging, and history counts only real briefs.

GET /api/digest?date= used to go unchecked until the agent parsed it, after the
20-token charge. And /digest/history/dates counted failed or still-running runs
that get_digests_for_date never returns, so BriefPage could open an empty day.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_engine.briefing_agent as briefing_agent
import database
from auth import get_current_user
from database import Base
from models.db_models import Execution, Report, User
from routers import digest as digest_router
from services import digest_service, report_service, token_service


@pytest.fixture
def client(monkeypatch):
    charges: list[str] = []
    runs: list[dict] = []

    def _fake_deduct(user_id, subject_id, db):
        charges.append(subject_id)
        return True, 42

    def _fake_run_digest(**kwargs):
        runs.append(kwargs)
        raise AssertionError("agent must not run for a bad date")

    monkeypatch.setattr(token_service, "deduct_for_digest", _fake_deduct)
    monkeypatch.setattr(briefing_agent, "run_digest", _fake_run_digest)
    monkeypatch.setattr(report_service, "save_report", lambda *a, **k: None)
    monkeypatch.setattr(report_service, "update_execution_status", lambda *a, **k: None)
    monkeypatch.setattr(digest_router, "get_share_url", lambda _id: None)

    app = FastAPI()
    app.include_router(digest_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, email=None)
    app.dependency_overrides[database.get_db] = lambda: None
    return TestClient(app), charges, runs


@pytest.mark.parametrize("bad", ["2026-13-45", "11/16/2026", "2026-02-30", "2026-1-5", ""])
def test_bad_date_is_400_without_charge(client, bad):
    c, charges, runs = client
    r = c.get("/api/digest", params={"date": bad})
    assert r.status_code == 400
    assert "YYYY-MM-DD" in r.json()["detail"]
    assert charges == []
    assert runs == []


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, email="b@example.com", hashed_password="x"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _add_run(db, ex_id, slot, created_at, status, with_report):
    db.add(
        Execution(
            id=ex_id,
            execution_type="daily_digest",
            subject_type="user_date",
            subject_id=f"1:{slot}",
            creator_id=1,
            created_at=created_at,
            status=status,
        )
    )
    if with_report:
        db.add(Report(execution_id=ex_id, report_type="daily_digest", content="brief", created_at=created_at))
    db.commit()


def test_history_counts_only_completed_briefs(db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date().isoformat()
    _add_run(db, 1, today, now, "completed", True)
    _add_run(db, 2, today, now, "failed", False)
    _add_run(db, 3, today, now, "running", False)

    dates, counts = digest_service.get_digest_dates(db, 1, 7)
    briefs = digest_service.get_digests_for_date(db, 1, today)

    assert counts == {today: 1}
    assert dates == [today]
    assert len(briefs) == counts[today]


def test_day_with_only_failed_run_is_not_listed(db):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date().isoformat()
    _add_run(db, 1, today, now, "failed", False)
    # A failed run that somehow kept a report still is not a finished brief.
    _add_run(db, 2, f"w:{today}", now, "failed", True)

    dates, counts = digest_service.get_digest_dates(db, 1, 7)

    assert dates == []
    assert counts == {}
    assert digest_service.get_digests_for_date(db, 1, today) == []

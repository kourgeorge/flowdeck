"""GET /api/data/reports/{ticker}?date= must match the requested run or refuse.

It used to fall back to the latest run with 200 when nothing matched, so
date='1' and date='2026-03-05' both silently returned a different run.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from auth import get_current_user
from models.db_models import Execution, User
from routers import data_api
from services import report_service


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(report_service, "SessionLocal", sessions)

    db = sessions()
    user = User(email="u@example.com")
    db.add(user)
    db.flush()
    for ex_id, subject, created in (
        (1, "AAPL", datetime(2026, 3, 4, 10, 0)),
        (2, "AAPL", datetime(2026, 11, 10, 9, 30)),
        (3, "MSFT", datetime(2026, 3, 4, 11, 0)),
    ):
        db.add(Execution(
            id=ex_id, execution_type="ticker", subject_type="ticker", subject_id=subject,
            creator_id=user.id, status="completed", created_at=created,
        ))
    db.commit()
    db.close()

    svc = report_service.ReportService()
    gateway = SimpleNamespace(
        get_quote=lambda t: {"symbol": t},
        get_analysis_run_for_date=svc.get_analysis_run_for_date,
        get_latest_execution_for_ticker=svc.get_latest_execution_for_ticker,
        get_reports_with_scores=lambda ex_id: {"market_report": {"content": f"run {ex_id}"}},
    )
    monkeypatch.setattr(data_api, "get_data_gateway", lambda: gateway)

    app = FastAPI()
    app.include_router(data_api.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    return TestClient(app)


def test_matching_date_returns_that_run(client):
    r = client.get("/api/data/reports/AAPL", params={"date": "2026-03-04"})
    assert r.status_code == 200
    assert r.json()["report_run_id"] == 1


def test_run_id_returns_that_run(client):
    r = client.get("/api/data/reports/aapl", params={"date": "1"})
    assert r.status_code == 200
    assert r.json()["report_run_id"] == 1


def test_run_id_of_other_ticker_is_404(client):
    r = client.get("/api/data/reports/AAPL", params={"date": "3"})
    assert r.status_code == 404


def test_unknown_run_id_is_404(client):
    r = client.get("/api/data/reports/AAPL", params={"date": "999"})
    assert r.status_code == 404


def test_unmatched_date_is_404_not_latest(client):
    r = client.get("/api/data/reports/AAPL", params={"date": "2026-03-05"})
    assert r.status_code == 404
    assert "2026-03-05" in r.json()["detail"]


def test_no_date_returns_latest(client):
    r = client.get("/api/data/reports/AAPL")
    assert r.status_code == 200
    assert r.json()["report_run_id"] == 2


@pytest.mark.parametrize("bad", ["yesterday", "2026-13-01", "1a", "2026/03/04"])
def test_garbage_date_is_400(client, bad):
    r = client.get("/api/data/reports/AAPL", params={"date": bad})
    assert r.status_code == 400


@pytest.fixture
def lenient_client(client):
    # Return a 500 response instead of re-raising, so a crash fails the
    # status assertion rather than surfacing as a test error.
    return TestClient(client.app, raise_server_exceptions=False)


@pytest.mark.parametrize("bad", ["²", "1²", "١٢"])
def test_non_ascii_digits_are_400(lenient_client, bad):
    r = lenient_client.get("/api/data/reports/AAPL", params={"date": bad})
    assert r.status_code == 400


@pytest.mark.parametrize("huge", ["99999999999999999999", str(2**63)])
def test_run_id_too_big_for_db_is_404(lenient_client, huge):
    r = lenient_client.get("/api/data/reports/AAPL", params={"date": huge})
    assert r.status_code == 404

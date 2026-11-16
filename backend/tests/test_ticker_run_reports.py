"""GET /api/tickers/{ticker}/reports/{run_id} must only serve that ticker's analysis runs.

Execution ids are one shared counter, so the route used to hand back any
execution's reports: other users' private daily_digest briefs (even to a
logged-out caller) and an MSFT run under /api/tickers/AAPL/....
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
from auth import get_current_user_optional
from models.db_models import Execution, Report, User
from routers import tickers
from services import report_service

ALICE_BRIEF = "Alice's brief: your TSLA and NVDA holdings ..."


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(report_service, "SessionLocal", sessions)

    db = sessions()
    alice = User(email="alice@example.com")
    bob = User(email="bob@example.com")
    db.add_all([alice, bob])
    db.flush()
    created = datetime(2026, 11, 10, 9, 30)
    rows = [
        (1, "ticker", "ticker", "AAPL", "market_report", "AAPL market view"),
        (3, "ticker", "ticker", "MSFT", "market_report", "MSFT market view"),
        (77, "daily_digest", "user", str(alice.id), "daily_digest", ALICE_BRIEF),
        # A digest that happens to carry a ticker subject must still be refused:
        # the execution type, not just the subject, decides what is public.
        (78, "daily_digest", "ticker", "AAPL", "daily_digest", ALICE_BRIEF),
    ]
    for ex_id, ex_type, subj_type, subj_id, report_type, content in rows:
        db.add(Execution(
            id=ex_id, execution_type=ex_type, subject_type=subj_type, subject_id=subj_id,
            creator_id=alice.id, status="completed", created_at=created,
        ))
        db.add(Report(execution_id=ex_id, report_type=report_type, content=content))
    db.commit()
    bob_id = bob.id
    db.close()

    svc = report_service.ReportService()
    gateway = SimpleNamespace(
        get_analysis_run_for_date=svc.get_analysis_run_for_date,
        get_reports_with_scores=svc.get_reports_with_scores,
    )
    monkeypatch.setattr(tickers, "get_data_gateway", lambda: gateway)

    def _make(user=None):
        app = FastAPI()
        app.include_router(tickers.router)
        app.dependency_overrides[get_current_user_optional] = lambda: user
        return TestClient(app)

    _make.bob = SimpleNamespace(id=bob_id)
    return _make


def _url(ticker, run_id):
    return f"{tickers.router.prefix}/{ticker}/reports/{run_id}"


@pytest.mark.parametrize("run_id", [77, 78])
def test_daily_digest_is_404_without_login(make_client, run_id):
    r = make_client(None).get(_url("AAPL", run_id))
    assert r.status_code == 404
    assert ALICE_BRIEF not in r.text


@pytest.mark.parametrize("run_id", [77, 78])
def test_daily_digest_is_404_for_other_user(make_client, run_id):
    r = make_client(make_client.bob).get(_url("AAPL", run_id))
    assert r.status_code == 404
    assert ALICE_BRIEF not in r.text


def test_other_tickers_run_is_404(make_client):
    r = make_client(None).get(_url("AAPL", 3))
    assert r.status_code == 404
    assert "MSFT" not in r.text


def test_missing_and_forbidden_ids_look_the_same(make_client):
    client = make_client(None)
    missing = client.get(_url("AAPL", 999))
    digest = client.get(_url("AAPL", 77))
    assert missing.status_code == digest.status_code == 404
    assert missing.json() == digest.json()


@pytest.mark.parametrize("ticker", ["AAPL", "aapl"])
def test_own_ticker_run_is_served(make_client, ticker):
    r = make_client(None).get(_url(ticker, 1))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"market_report"}
    assert body["market_report"]["content"] == "AAPL market view"

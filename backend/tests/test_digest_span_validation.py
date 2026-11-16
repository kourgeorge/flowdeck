"""GET /api/digest must refuse unknown span values before charging.

span used to be a free string: 'monthly' / 'Daily' / 'custom' were billed with
the weekly subject (user:w:DATE) while the agent ran a daily brief.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_engine.briefing_agent as briefing_agent
import database
from auth import get_current_user
from routers import digest as digest_router
from services import digest_service, report_service, token_service


@pytest.fixture
def harness(monkeypatch):
    charges: list[str] = []
    runs: list[dict] = []

    def _fake_deduct(user_id, subject_id, db):
        charges.append(subject_id)
        return True, 42

    def _fake_run_digest(**kwargs):
        runs.append(kwargs)
        return SimpleNamespace(
            narrative="n",
            what_to_watch="w",
            digest_date=kwargs["digest_date"],
            priority_tickers=[],
            span_type=kwargs["span_type"],
            span_label=kwargs["span_type"].capitalize(),
        )

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


@pytest.mark.parametrize("span", ["monthly", "Daily", "custom"])
def test_unknown_span_is_422_without_charge(harness, span):
    client, charges, runs = harness
    r = client.get("/api/digest", params={"span": span, "date": "2026-11-16"})
    assert r.status_code == 422
    assert charges == []
    assert runs == []


def test_daily_uses_date_slot(harness):
    client, charges, runs = harness
    r = client.get("/api/digest", params={"span": "daily", "date": "2026-11-16"})
    assert r.status_code == 200
    assert charges == ["7:2026-11-16"]
    assert runs[0]["span_type"] == "daily"
    assert r.json()["span_type"] == "daily"


def test_default_span_is_daily(harness):
    client, charges, runs = harness
    r = client.get("/api/digest", params={"date": "2026-11-16"})
    assert r.status_code == 200
    assert charges == ["7:2026-11-16"]
    assert runs[0]["span_type"] == "daily"


def test_weekly_uses_w_slot(harness):
    client, charges, runs = harness
    r = client.get("/api/digest", params={"span": "weekly", "date": "2026-11-16"})
    assert r.status_code == 200
    assert charges == ["7:w:2026-11-16"]
    assert runs[0]["span_type"] == "weekly"
    assert r.json()["span_type"] == "weekly"


@pytest.mark.parametrize("span", ["monthly", "Daily", "custom", ""])
def test_service_helpers_refuse_unknown_span(span):
    with pytest.raises(ValueError):
        digest_service._build_slot(span, "2026-11-16")
    with pytest.raises(ValueError):
        digest_service._parse_span(span)

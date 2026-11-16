"""Any failure after the brief is charged must mark the run failed and refund once.

The handler used to cover only run_digest. When save_report raised
("database is locked") the user was charged, nothing was saved, and the
Execution stayed "running". A client disconnect (asyncio.CancelledError) also
skipped the refund because the handler was `except Exception`.
"""

from __future__ import annotations

import asyncio
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
from services import digest_service, info_fetcher, report_service, token_service


def _result():
    return SimpleNamespace(
        narrative="Markets were calm.",
        what_to_watch="CPI on Thursday.",
        digest_date="2026-11-16",
        priority_tickers=["AAPL"],
        important_events=[],
        span_type="daily",
        span_label="Daily",
        references=[],
        resources=None,
        agent_steps=None,
        focus_snapshot=None,
    )


def _patch(monkeypatch, *, run=None, save=None):
    calls = {"status": [], "refunds": [], "saved": []}
    monkeypatch.setattr(token_service, "deduct_for_digest", lambda user_id, subject_id, db: (True, 42))
    monkeypatch.setattr(briefing_agent, "run_digest", run or (lambda **kw: _result()))
    monkeypatch.setattr(info_fetcher, "get_info_fetcher", lambda: None)

    def _save(execution_id, report_type, **kw):
        if save is not None:
            save()
        calls["saved"].append(execution_id)

    monkeypatch.setattr(report_service, "save_report", _save)
    monkeypatch.setattr(
        report_service,
        "update_execution_status",
        lambda execution_id, status, **kw: calls["status"].append((execution_id, status)),
    )

    def _refund(execution_id, db):
        calls["refunds"].append(execution_id)
        return True

    monkeypatch.setattr(token_service, "refund_for_failed_digest", _refund)
    return calls


def test_save_report_failure_marks_failed_and_refunds_once(monkeypatch):
    def _locked():
        raise RuntimeError("database is locked")

    calls = _patch(monkeypatch, save=_locked)
    app = FastAPI()
    app.include_router(digest_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, email=None)
    app.dependency_overrides[database.get_db] = lambda: None
    r = TestClient(app).get("/api/digest", params={"date": "2026-11-16"})

    assert r.status_code == 500
    assert "database is locked" not in r.json()["detail"]
    assert calls["status"] == [(42, "failed")]
    assert calls["refunds"] == [42]


def test_cancelled_run_marks_failed_and_refunds_once(monkeypatch):
    def _cancel(**kw):
        raise asyncio.CancelledError()

    calls = _patch(monkeypatch, run=_cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            digest_service.run_and_store_digest(
                None, 7, digest_date="2026-11-16", span_type="daily"
            )
        )

    assert calls["status"] == [(42, "failed")]
    assert calls["refunds"] == [42]
    assert calls["saved"] == []


def test_success_response_includes_execution_id(monkeypatch):
    calls = _patch(monkeypatch)
    monkeypatch.setattr(digest_router, "get_share_url", lambda execution_id: None)
    app = FastAPI()
    app.include_router(digest_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, email=None)
    app.dependency_overrides[database.get_db] = lambda: None
    r = TestClient(app).get("/api/digest", params={"date": "2026-11-16"})

    assert r.status_code == 200, r.text
    assert r.json()["execution_id"] == 42
    assert calls["status"] == [(42, "completed")]
    assert calls["refunds"] == []

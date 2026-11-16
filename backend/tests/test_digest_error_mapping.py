"""GET /api/digest must send 402 only when the balance check fails.

The router used to map every RuntimeError to 402 "Purchase Tokens", so an
unrelated crash inside the digest told the user to buy tokens.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_engine.briefing_agent as briefing_agent
import database
from auth import get_current_user
from routers import digest as digest_router
from services import report_service, token_service


def _client(monkeypatch, *, deduct_ok: bool, run_error: Exception | None = None):
    monkeypatch.setattr(
        token_service,
        "deduct_for_digest",
        lambda user_id, subject_id, db: (True, 42) if deduct_ok else (False, None),
    )

    def _fake_run_digest(**kwargs):
        if run_error is not None:
            raise run_error
        raise AssertionError("run_digest should not be reached")

    monkeypatch.setattr(briefing_agent, "run_digest", _fake_run_digest)
    monkeypatch.setattr(report_service, "update_execution_status", lambda *a, **k: None)
    monkeypatch.setattr(token_service, "refund_for_failed_digest", lambda *a, **k: True)

    app = FastAPI()
    app.include_router(digest_router.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, email=None)
    app.dependency_overrides[database.get_db] = lambda: None
    return TestClient(app)


def test_insufficient_balance_is_402(monkeypatch):
    client = _client(monkeypatch, deduct_ok=False)
    r = client.get("/api/digest", params={"date": "2026-11-16"})
    assert r.status_code == 402
    assert "Purchase Tokens" in r.json()["detail"]


def test_unrelated_runtime_error_is_500_not_402(monkeypatch):
    client = _client(monkeypatch, deduct_ok=True, run_error=RuntimeError("event loop closed"))
    r = client.get("/api/digest", params={"date": "2026-11-16"})
    assert r.status_code == 500
    assert "Purchase Tokens" not in r.json()["detail"]

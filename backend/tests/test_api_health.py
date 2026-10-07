"""/api/health: the publicly reachable readiness check for uptime monitors."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
import main


def _client():
    # No context manager: entering TestClient runs the app lifespan, which
    # starts background schedulers this test doesn't need.
    return TestClient(main.app)


def test_api_health_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "engine", create_engine(f"sqlite:///{tmp_path}/ok.db"))
    resp = _client().get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "service": "tradingagents-api", "database": "ok"}


def test_api_health_returns_503_when_database_unreachable(tmp_path, monkeypatch):
    # Parent directory doesn't exist, so SQLite fails on connect.
    broken = create_engine(f"sqlite:///{tmp_path}/missing/dir/x.db")
    monkeypatch.setattr(database, "engine", broken)
    resp = _client().get("/api/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "unhealthy"
    # Public route: the underlying error text must not leak.
    assert "sqlite" not in resp.text.lower()


def test_plain_health_stays_process_only(tmp_path, monkeypatch):
    # Docker healthchecks hit /health; a DB outage must not fail it and
    # trigger container restarts.
    monkeypatch.setattr(database, "engine", create_engine(f"sqlite:///{tmp_path}/missing/dir/x.db"))
    assert _client().get("/health").status_code == 200

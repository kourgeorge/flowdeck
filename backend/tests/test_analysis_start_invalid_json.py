"""POST /api/analyses/start must return the documented 400 for an unparseable body.

It used to return 422, because the ValueError catch around request.json() also
caught JSONDecodeError, leaving the 400 branch unreachable.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app_services
import database
from auth import get_current_user


def _client(monkeypatch):
    from routers import analyses

    service = Mock()
    gateway = Mock()
    monkeypatch.setattr(app_services, "get_analysis_service", lambda: service)
    monkeypatch.setattr(analyses, "get_data_gateway", lambda: gateway)
    app = FastAPI()
    app.include_router(analyses.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, email="t@example.com")
    app.dependency_overrides[database.get_db] = lambda: None
    return TestClient(app), service, gateway


def test_broken_json_returns_400(monkeypatch):
    client, service, gateway = _client(monkeypatch)
    resp = client.post(
        "/api/analyses/start",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid JSON in request body"}
    gateway.get_quote.assert_not_called()
    service.start_analysis.assert_not_called()


def test_valid_json_that_is_not_an_object_stays_422(monkeypatch):
    client, service, _ = _client(monkeypatch)
    resp = client.post("/api/analyses/start", json=["AAPL"])
    assert resp.status_code == 422
    service.start_analysis.assert_not_called()

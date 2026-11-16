"""GET /api/share/{token} is the one route that serves report content with no login.

Anyone holding a token can read the report behind it, including a user's
private daily brief, so every bad or half-broken input must end in a clean
404 (never a 500 that leaks a traceback, never the wrong report).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from models.db_models import Execution, Report, User
from routers import share
from services.share_service import encode_share_token

CREATED = datetime(2026, 11, 10, 9, 30)
AAPL_REPORTS = {"final_trade_decision": "BUY AAPL on strong services growth"}


class FakeGateway:
    def __init__(self, reports=None, company_info=None, info_error=None):
        self.reports = AAPL_REPORTS if reports is None else reports
        self.company_info = company_info if company_info is not None else {"name": "Apple Inc."}
        self.info_error = info_error

    def get_reports_with_scores(self, execution_id, execution_type=None):
        return self.reports

    def get_company_info(self, ticker):
        if self.info_error:
            raise self.info_error
        return self.company_info


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARE_SECRET_KEY", Fernet.generate_key().decode())
    engine = create_engine(f"sqlite:///{tmp_path / 'share.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(share, "SessionLocal", sessions)

    db = sessions()
    alice = User(email="alice@example.com")
    db.add(alice)
    db.flush()
    db.add_all([
        Execution(id=1, execution_type="ticker", subject_type="ticker", subject_id="aapl",
                  creator_id=alice.id, status="completed", created_at=CREATED),
        Execution(id=2, execution_type="daily_digest", subject_type="user_date", subject_id=f"{alice.id}:2026-11-10",
                  creator_id=alice.id, status="completed", created_at=CREATED),
        Execution(id=3, execution_type="chat", subject_type="user", subject_id=str(alice.id),
                  creator_id=alice.id, status="completed", created_at=CREATED),
        # A digest run that never wrote its Report row (e.g. it failed half-way).
        Execution(id=4, execution_type="daily_digest", subject_type="user_date", subject_id=f"{alice.id}:2026-11-09",
                  creator_id=alice.id, status="failed", created_at=CREATED),
        Execution(id=5, execution_type="daily_digest", subject_type="user_date", subject_id=f"{alice.id}:2026-11-08",
                  creator_id=alice.id, status="completed", created_at=CREATED),
    ])
    db.add(Report(
        execution_id=2, report_type="daily_digest", content="Markets were mixed today.",
        metadata_json=json.dumps({
            "what_to_watch": "Fed minutes tomorrow.",
            "digest_date": "2026-11-10",
            "span_type": "weekly",
            "span_label": "Weekly",
            "priority_tickers": ["AAPL", "MSFT"],
            "important_events": [{"title": "CPI print"}],
        }),
    ))
    db.add(Report(execution_id=5, report_type="daily_digest", content="Short brief.", metadata_json="{not json"))
    db.commit()
    db.close()

    def _client(gateway=None):
        gw = gateway or FakeGateway()
        monkeypatch.setattr(share, "get_data_gateway", lambda: gw)
        app = FastAPI()
        app.include_router(share.router)
        return TestClient(app, raise_server_exceptions=False)

    return SimpleNamespace(client=_client)


def _get(client, execution_id):
    token = encode_share_token(execution_id)
    assert token
    return client.get(f"/api/share/{token}")


def test_garbage_token_is_invalid_link(env):
    r = env.client().get("/api/share/not-a-token")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_non_ascii_token_is_404_not_500(env):
    r = env.client().get("/api/share/tökén-☃")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_token_signed_with_key_but_not_an_object_is_404(env):
    import os

    fernet = Fernet(os.environ["SHARE_SECRET_KEY"].encode())
    token = fernet.encrypt(b"[1, 2]").decode()
    r = env.client().get(f"/api/share/{token}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_token_with_boolean_id_is_404_not_execution_1(env):
    import os

    fernet = Fernet(os.environ["SHARE_SECRET_KEY"].encode())
    token = fernet.encrypt(b'{"e": true}').decode()
    r = env.client().get(f"/api/share/{token}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_token_from_another_key_is_invalid_link(env):
    other = Fernet(Fernet.generate_key()).encrypt(b'{"e": 2}').decode()
    r = env.client().get(f"/api/share/{other}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_unset_share_key_rejects_every_token(env, monkeypatch):
    token = encode_share_token(2)
    monkeypatch.delenv("SHARE_SECRET_KEY")
    r = env.client().get(f"/api/share/{token}")
    assert r.status_code == 404
    assert r.json()["detail"] == "Invalid or expired link"


def test_unknown_execution_id_is_report_not_found(env):
    r = _get(env.client(), 999)
    assert r.status_code == 404
    assert r.json()["detail"] == "Report not found"


def test_execution_type_without_resolver_is_404(env):
    r = _get(env.client(), 3)
    assert r.status_code == 404
    assert "chat" in r.json()["detail"]


def test_daily_digest_without_report_row_is_404(env):
    r = _get(env.client(), 4)
    assert r.status_code == 404
    assert r.json()["detail"] == "Report not found"


def test_daily_digest_with_broken_metadata_uses_defaults(env):
    r = _get(env.client(), 5)
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] == "Short brief."
    assert body["span_type"] == "daily"
    assert body["span_label"] == "Daily"
    assert body["priority_tickers"] == []
    assert body["agent_steps"] == []
    assert body["important_events"] == []


def test_ticker_with_no_reports_is_404(env):
    r = _get(env.client(FakeGateway(reports={})), 1)
    assert r.status_code == 404
    assert r.json()["detail"] == "Report not found"


def test_ticker_company_info_failure_still_returns_report(env):
    r = _get(env.client(FakeGateway(info_error=RuntimeError("info service down"))), 1)
    assert r.status_code == 200
    body = r.json()
    assert body["company_name"] is None
    assert body["reports"] == AAPL_REPORTS


def test_valid_ticker_token_returns_report(env):
    r = _get(env.client(), 1)
    assert r.status_code == 200
    assert r.json() == {
        "type": "ticker",
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "execution_id": 1,
        "report_date": "2026-11-10",
        "reports": AAPL_REPORTS,
    }


def test_valid_daily_digest_token_returns_brief(env):
    r = _get(env.client(), 2)
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "digest"
    assert body["execution_id"] == 2
    assert body["narrative"] == "Markets were mixed today."
    assert body["what_to_watch"] == "Fed minutes tomorrow."
    assert body["digest_date"] == "2026-11-10"
    assert body["span_type"] == "weekly"
    assert body["span_label"] == "Weekly"
    assert body["priority_tickers"] == ["AAPL", "MSFT"]
    assert body["important_events"] == [{"title": "CPI print"}]

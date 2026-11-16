"""ReportService must not hand out an execution's reports unless the caller
names the execution type it expects.

Execution ids are one shared counter for ticker runs and private per-user
runs such as daily_digest, so a bare id lookup is only safe while every
caller checks the id first. These tests pin the safe-by-default behaviour.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from models.db_models import Execution, Report, User
from services import report_service

BRIEF = "Alice's private brief"


@pytest.fixture
def svc(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(report_service, "SessionLocal", sessions)

    db = sessions()
    alice = User(email="alice@example.com")
    db.add(alice)
    db.flush()
    created = datetime(2026, 11, 10, 9, 30)
    for ex_id, ex_type, subj_type, subj_id, rtype, content in [
        (1, "ticker", "ticker", "AAPL", "market_report", "AAPL market view"),
        (77, "daily_digest", "user", str(alice.id), "daily_digest", BRIEF),
    ]:
        db.add(Execution(
            id=ex_id, execution_type=ex_type, subject_type=subj_type, subject_id=subj_id,
            creator_id=alice.id, status="completed", created_at=created,
        ))
        db.add(Report(execution_id=ex_id, report_type=rtype, content=content))
    db.commit()
    db.close()
    return report_service.ReportService()


def test_ticker_execution_still_served_as_ticker(svc):
    assert svc.get_reports_for_execution(1, execution_type="ticker")["market_report"]["content"] == "AAPL market view"
    assert svc.get_reports_with_scores(1, execution_type="ticker")["market_report"]["content"] == "AAPL market view"
    assert svc.get_reports_for_run(1, execution_type="ticker") == {"market_report": "AAPL market view"}


@pytest.mark.parametrize("method", ["get_reports_for_execution", "get_reports_with_scores", "get_reports_for_run"])
def test_daily_digest_refused_when_ticker_expected(svc, method):
    assert getattr(svc, method)(77, execution_type="ticker") == {}


@pytest.mark.parametrize("method", ["get_reports_for_execution", "get_reports_with_scores", "get_reports_for_run"])
def test_daily_digest_refused_with_empty_type(svc, method):
    assert getattr(svc, method)(77, execution_type="") == {}


@pytest.mark.parametrize("method", ["get_reports_for_execution", "get_reports_with_scores", "get_reports_for_run"])
def test_execution_type_is_required(svc, method):
    with pytest.raises(TypeError):
        getattr(svc, method)(77)


def test_daily_digest_served_only_when_asked_for(svc):
    assert svc.get_reports_for_execution(77, execution_type="daily_digest")["daily_digest"]["content"] == BRIEF
    assert svc.get_reports_for_run(77, execution_type="daily_digest") == {"daily_digest": BRIEF}

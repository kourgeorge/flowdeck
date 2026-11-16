"""Pin the status values get_analysis_status returns, so the docs cannot drift from the code."""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
from models.db_models import Execution
from services import data_cache
from services.analysis_service import AnalysisService


@pytest.fixture
def service(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(data_cache, "_store", data_cache._SQLiteTTLStore(str(tmp_path / "cache.sqlite"), 128))
    return AnalysisService(), sessions


def _add_run(sessions, run_id, status, error=None):
    with sessions() as db:
        db.add(Execution(id=run_id, execution_type="ticker", subject_type="ticker", creator_id=1, subject_id="AAPL", status=status,
                         error_message=error, created_at=datetime(2026, 1, 2)))
        db.commit()


def test_failed_run_reports_error(service):
    svc, sessions = service
    _add_run(sessions, 1, "failed", "boom")
    result = svc.get_analysis_status(1)
    assert result["status"] == "error"
    assert result["error"] == "boom"


def test_stopped_run_reports_error_once_cleaned_up(service):
    # A stop is stored as "failed" (see _fail_analysis), and the live "cancelled" status is
    # deleted from the cache, so the endpoint returns "error" for it.
    svc, sessions = service
    _add_run(sessions, 2, "failed", "Analysis cancelled")
    assert svc.get_analysis_status(2)["status"] == "error"


def test_completed_run_reports_completed(service):
    svc, sessions = service
    _add_run(sessions, 3, "completed")
    assert svc.get_analysis_status(3)["status"] == "completed"

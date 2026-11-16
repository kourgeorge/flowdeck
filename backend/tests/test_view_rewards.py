"""Viewer rewards: token_service.record_view must not pay for self-views, past the
per-report cap, or after the reward window, and must ignore missing runs."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import database
from models.db_models import Execution, ReportView, Usage, User
from services import token_service


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path}/views.db', connect_args={'check_same_thread': False})
    event.listen(engine, 'connect', database._set_sqlite_pragmas)
    database.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([User(id=1, email='creator@example.test'), User(id=2, email='viewer@example.test')])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _run(db, earned_tokens=0, created_at=None):
    ex = Execution(execution_type='ticker', subject_type='ticker', subject_id='AAPL', creator_id=1,
                   status='completed', earned_tokens=earned_tokens,
                   created_at=created_at or datetime.utcnow())
    db.add(ex)
    db.commit()
    return ex.id


def _rewards(db):
    return db.query(Usage).filter_by(transaction_type='view_reward').count()


def test_new_viewer_on_fresh_run_is_rewarded(db):
    # Baseline so the "no reward" tests below cannot pass just because rewards never happen.
    run = _run(db)
    assert token_service.record_view(run, 2, db) is True
    assert _rewards(db) == 1
    assert db.get(Execution, run).earned_tokens == 1


def test_creator_viewing_own_run_records_view_without_reward(db):
    run = _run(db)
    before = token_service.get_balance(1, db)
    assert token_service.record_view(run, 1, db) is True
    assert db.query(ReportView).filter_by(execution_id=run, viewer_id=1).count() == 1
    assert token_service.get_balance(1, db) == before
    assert _rewards(db) == 0
    db.expire_all()
    assert db.get(Execution, run).earned_tokens == 0


def test_run_at_reward_cap_gives_no_view_reward(db):
    run = _run(db, earned_tokens=token_service.MAX_REWARD_PER_REPORT)
    assert token_service.MAX_REWARD_PER_REPORT == 400
    assert token_service.record_view(run, 2, db) is True
    assert _rewards(db) == 0
    db.expire_all()
    assert db.get(Execution, run).earned_tokens == 400


def test_run_older_than_reward_window_gives_no_view_reward(db):
    run = _run(db, created_at=datetime.utcnow() - timedelta(days=15))
    assert token_service.REWARD_WINDOW_DAYS == 14
    assert token_service.record_view(run, 2, db) is True
    assert _rewards(db) == 0
    db.expire_all()
    assert db.get(Execution, run).earned_tokens == 0


def test_missing_run_returns_false_and_records_nothing(db):
    assert token_service.record_view(999, 2, db) is False
    assert db.query(ReportView).count() == 0
    assert _rewards(db) == 0

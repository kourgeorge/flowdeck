"""The models file must be loaded once, under the name the app uses (models.db_models).

The brief's history loader used to import backend.models.db_models. When a test that
ran the brief came before one that imported a backend service, the same file was
loaded twice and SQLAlchemy raised "Table 'entity_sequences' is already defined".
Since T-87 the query lives in services.digest_service (which uses models.db_models)
and ai_engine does not import the models at all.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]

from models import db_models
from ai_engine.briefing_agent import runner
from services import digest_service


class _RecordingDb:
    """Records the model classes the loader queries, then returns no rows."""

    def __init__(self):
        self.queried = None

    def query(self, *models):
        self.queried = models
        return self

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


def test_recent_briefs_loader_queries_the_apps_model_classes():
    db = _RecordingDb()

    assert runner._load_recent_digest_briefs(7, db, loader=digest_service.load_recent_digest_rows) == []
    assert db.queried == (db_models.Execution, db_models.Report)


def test_running_the_brief_first_does_not_break_later_model_imports():
    # The bug only shows when the brief runs before anything imports models.db_models,
    # so this needs a fresh interpreter; inside pytest the order depends on the suite.
    script = (
        "from ai_engine.briefing_agent import runner\n"
        "runner._load_recent_digest_briefs(7, object())\n"
        "import sys\n"
        "assert 'backend.models.db_models' not in sys.modules, 'loaded under backend name'\n"
        "assert 'models.db_models' not in sys.modules, 'ai_engine imported backend models'\n"
        "from models.db_models import Execution\n"
        "print('ok')\n"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(REPO_ROOT / "backend")])}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().endswith("ok")


def test_recent_briefs_loader_with_no_db_returns_empty():
    assert runner._load_recent_digest_briefs(7, None) == []


def test_recent_briefs_loader_returns_empty_when_db_is_not_a_session():
    # run_digest is called with db=object() in the brief tests; the loader must not raise.
    assert runner._load_recent_digest_briefs(7, object()) == []
    assert runner._load_recent_digest_briefs(7, object(), loader=digest_service.load_recent_digest_rows) == []


def test_recent_briefs_without_loader_are_empty():
    db = _RecordingDb()
    assert runner._load_recent_digest_briefs(7, db) == []
    assert db.queried is None


def test_recent_briefs_are_built_from_the_loaded_rows():
    from datetime import datetime

    execution = type("E", (), {"created_at": datetime(2026, 11, 15, 8, 0)})()
    report = type("R", (), {
        "content": " story ",
        "metadata_json": '{"digest_date": "2026-11-15", "priority_tickers": ["AAA"], "what_to_watch": "w"}',
    })()
    seen = []

    def loader(uid, db, limit):
        seen.append((uid, limit))
        return [(execution, report)]

    (brief,) = runner._load_recent_digest_briefs(7, object(), loader=loader)
    assert seen == [(7, 5)]
    assert (brief.narrative, brief.what_to_watch, brief.digest_date) == ("story", "w", "2026-11-15")
    assert brief.priority_tickers == ["AAA"] and brief.created_at == "2026-11-15T08:00:00+00:00"


def test_portfolio_tickers_loader_queries_subscriptions():
    class _Db(_RecordingDb):
        def all(self):
            return [type("S", (), {"ticker": "aaa"})()]

    db = _Db()
    assert digest_service.load_portfolio_tickers(7, db) == ["AAA"]
    assert db.queried == (db_models.Subscription,)

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import Execution, Report, User
from services.digest_service import _report_to_brief_item, get_digest_dates, get_digests_for_date


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls(2026, 3, 17, 12, 0, 0)
        return cls(2026, 3, 17, 12, 0, 0, tzinfo=tz)


class _ExecutionStub:
    def __init__(self, execution_id: int, created_at: datetime | None) -> None:
        self.id = execution_id
        self.created_at = created_at


class _ReportStub:
    def __init__(self, content: str = "", metadata_json: str | None = None) -> None:
        self.content = content
        self.metadata_json = metadata_json


class TestDigestService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="briefs@example.com", hashed_password="x"))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _add_digest(
        self,
        *,
        execution_id: int,
        subject_id: str,
        created_at: datetime,
        content: str = "Brief body",
    ) -> None:
        self.db.add(
            Execution(
                id=execution_id,
                execution_type="daily_digest",
                subject_type="user_date",
                subject_id=subject_id,
                creator_id=1,
                created_at=created_at,
            )
        )
        self.db.add(
            Report(
                execution_id=execution_id,
                report_type="daily_digest",
                content=content,
                created_at=created_at,
            )
        )
        self.db.commit()

    def test_report_to_brief_item_marks_naive_created_at_as_utc(self) -> None:
        execution = _ExecutionStub(
            execution_id=42,
            created_at=datetime(2026, 3, 17, 15, 45, 30),
        )
        report = _ReportStub(content="Brief body")

        brief = _report_to_brief_item(execution, report, "2026-03-17")

        self.assertEqual(brief.created_at, "2026-03-17T15:45:30+00:00")

    def test_report_to_brief_item_preserves_aware_utc_created_at(self) -> None:
        execution = _ExecutionStub(
            execution_id=43,
            created_at=datetime(2026, 3, 17, 15, 45, 30, tzinfo=timezone.utc),
        )
        report = _ReportStub(content="Brief body")

        brief = _report_to_brief_item(execution, report, "2026-03-17")

        self.assertEqual(brief.created_at, "2026-03-17T15:45:30+00:00")

    def test_report_to_brief_item_preserves_important_events(self) -> None:
        execution = _ExecutionStub(
            execution_id=44,
            created_at=datetime(2026, 3, 17, 15, 45, 30, tzinfo=timezone.utc),
        )
        report = _ReportStub(
            content="Brief body",
            metadata_json=json.dumps(
                {
                    "digest_date": "2026-03-17",
                    "priority_tickers": ["AAPL"],
                    "important_events": [
                        {
                            "ticker": "AAPL",
                            "importance_score": 4.0,
                            "event": {
                                "event_type": "price_spike_up",
                                "domain": "price_technical",
                                "detected_on": "2026-03-17",
                                "strength": "high",
                                "metadata": {"return_1d_pct": 5.2},
                            },
                        }
                    ],
                }
            ),
        )

        brief = _report_to_brief_item(execution, report, "2026-03-17")

        self.assertEqual(len(brief.important_events), 1)
        self.assertEqual(brief.important_events[0]["event"]["event_type"], "price_spike_up")

    def test_report_to_brief_item_preserves_resources_and_agent_steps(self) -> None:
        execution = _ExecutionStub(
            execution_id=45,
            created_at=datetime(2026, 3, 17, 15, 45, 30, tzinfo=timezone.utc),
        )
        report = _ReportStub(
            content="Brief body",
            metadata_json=json.dumps(
                {
                    "resources": [
                        {
                            "type": "digest_market_context",
                            "title": "Market context snapshot",
                        }
                    ],
                    "agent_steps": [
                        {
                            "agent": "Narrative Writer",
                            "kind": "llm_call",
                            "status": "completed",
                        }
                    ],
                }
            ),
        )

        brief = _report_to_brief_item(execution, report, "2026-03-17")

        self.assertEqual(brief.resources, [{"type": "digest_market_context", "title": "Market context snapshot"}])
        self.assertEqual(brief.agent_steps, [{"agent": "Narrative Writer", "kind": "llm_call", "status": "completed"}])

    def test_get_digest_dates_groups_daily_briefs_by_user_local_day(self) -> None:
        self._add_digest(
            execution_id=100,
            subject_id="1:2026-03-16",
            created_at=datetime(2026, 3, 16, 22, 9, 0),
        )

        with patch("services.digest_service.datetime", _FrozenDateTime):
            dates, count_by_date = get_digest_dates(
                self.db,
                1,
                7,
                timezone_name="Asia/Jerusalem",
            )

        self.assertEqual(dates, ["2026-03-17"])
        self.assertEqual(count_by_date, {"2026-03-17": 1})

    def test_get_digests_for_date_uses_local_day_bounds_for_daily_history(self) -> None:
        self._add_digest(
            execution_id=101,
            subject_id="1:2026-03-16",
            created_at=datetime(2026, 3, 16, 22, 9, 0),
            content="Midnight-local brief",
        )

        briefs = get_digests_for_date(
            self.db,
            1,
            "2026-03-17",
            timezone_name="Asia/Jerusalem",
        )
        previous_day_briefs = get_digests_for_date(
            self.db,
            1,
            "2026-03-16",
            timezone_name="Asia/Jerusalem",
        )

        self.assertEqual(len(briefs), 1)
        self.assertEqual(briefs[0].execution_id, 101)
        self.assertEqual(briefs[0].narrative, "Midnight-local brief")
        self.assertEqual(previous_day_briefs, [])


if __name__ == "__main__":
    unittest.main()

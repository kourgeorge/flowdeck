from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import (
    ApiKey,
    ChatMessage,
    ChatSession,
    ChatTurn,
    Execution,
    Report,
    ReportView,
    Subscription,
    Usage,
    User,
    UserProfile,
    UserSchedule,
)
from services.admin_service import build_analysis_reports_zip, delete_user


class TestAdminService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="admin@example.com", hashed_password="x", token_balance=1000))
        self.db.add(
            Execution(
                id=42,
                execution_type="ticker",
                subject_type="ticker",
                subject_id="AAPL",
                creator_id=1,
                status="completed",
                created_at=datetime(2026, 4, 7, 12, 0, 0),
            )
        )
        self.db.add_all(
            [
                Report(
                    id=10,
                    execution_id=42,
                    report_type="market_report",
                    content="Database market report",
                    metadata_json=json.dumps({"score": 8, "source": "db"}),
                    created_at=datetime(2026, 4, 7, 12, 1, 0),
                ),
                Report(
                    id=11,
                    execution_id=42,
                    report_type="final_trade_decision",
                    content="Database final decision",
                    metadata_json=json.dumps({"recommendation": "BUY"}),
                    created_at=datetime(2026, 4, 7, 12, 2, 0),
                ),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_build_analysis_reports_zip_includes_reports_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir) / "AAPL" / "42" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "market_report.md").write_text("Filesystem market report", encoding="utf-8")

            with patch("services.admin_service._results_root", return_value=Path(temp_dir)):
                payload = build_analysis_reports_zip(self.db, 42)

        self.assertIsNotNone(payload)
        zip_bytes, filename = payload or (b"", "")
        self.assertEqual(filename, "AAPL_analysis_42_reports.zip")

        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
            names = set(zf.namelist())
            self.assertIn("analysis.json", names)
            self.assertIn("reports/market_report.md", names)
            self.assertIn("reports/market_report.metadata.json", names)
            self.assertIn("reports/final_trade_decision.md", names)
            self.assertIn("reports/final_trade_decision.metadata.json", names)

            self.assertEqual(
                zf.read("reports/market_report.md").decode("utf-8"),
                "Filesystem market report",
            )
            self.assertEqual(
                zf.read("reports/final_trade_decision.md").decode("utf-8"),
                "Database final decision",
            )

            manifest = json.loads(zf.read("analysis.json").decode("utf-8"))
            self.assertEqual(manifest["analysis_run_id"], 42)
            self.assertEqual(manifest["ticker"], "AAPL")
            self.assertEqual(manifest["report_count"], 2)

    def test_delete_user_removes_owned_rows_without_database_cascades(self) -> None:
        self.db.add(User(id=2, email="delete@example.com", hashed_password="x", token_balance=100))
        self.db.add(UserProfile(user_id=2, persona_type="investor"))
        self.db.add(Subscription(user_id=2, ticker="AAPL"))
        self.db.add(
            Execution(
                id=43,
                execution_type="ticker",
                subject_type="ticker",
                subject_id="MSFT",
                creator_id=2,
                status="completed",
                created_at=datetime(2026, 4, 7, 13, 0, 0),
            )
        )
        self.db.add(
            Report(
                id=12,
                execution_id=43,
                report_type="market_report",
                content="User-owned report",
                created_at=datetime(2026, 4, 7, 13, 1, 0),
            )
        )
        self.db.add_all(
            [
                ReportView(id=1, execution_id=42, viewer_id=2),
                ReportView(id=2, execution_id=43, viewer_id=1),
            ]
        )
        self.db.add(ChatSession(id=100, user_id=2, title="Delete me"))
        self.db.add(ChatMessage(id=1000, session_id=100, role="user", content="hello", sort_order=1))
        self.db.add(ChatTurn(id=1001, session_id=100, user_id=2, status="completed"))
        self.db.add(ApiKey(id=1, user_id=2, key_hash="hash", key_prefix="fd_live_", name="test key"))
        self.db.add(Usage(id=1, user_id=2, amount=-10, balance_after=90, transaction_type="chat_cost"))
        self.db.add(
            UserSchedule(
                id=1,
                user_id=2,
                schedule_type="daily_digest",
                enabled=True,
                cron_expression="0 8 * * *",
            )
        )
        self.db.commit()

        self.assertTrue(delete_user(self.db, 2))

        self.assertIsNone(self.db.get(User, 2))
        self.assertEqual(self.db.query(UserProfile).filter(UserProfile.user_id == 2).count(), 0)
        self.assertEqual(self.db.query(Subscription).filter(Subscription.user_id == 2).count(), 0)
        self.assertIsNone(self.db.get(Execution, 43))
        self.assertIsNone(self.db.get(Report, 12))
        self.assertIsNone(self.db.get(ReportView, 1))
        self.assertIsNone(self.db.get(ReportView, 2))
        self.assertIsNone(self.db.get(ChatSession, 100))
        self.assertIsNone(self.db.get(ChatMessage, 1000))
        self.assertIsNone(self.db.get(ChatTurn, 1001))
        self.assertIsNone(self.db.get(ApiKey, 1))
        self.assertIsNone(self.db.get(Usage, 1))
        self.assertIsNone(self.db.get(UserSchedule, 1))
        self.assertIsNotNone(self.db.get(Execution, 42))


if __name__ == "__main__":
    unittest.main()

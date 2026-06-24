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
from services.admin_service import AdminUserDeletionError, build_analysis_reports_zip, delete_user


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

    def test_delete_user_rejects_admin_accounts(self) -> None:
        target_admin = User(
            id=2,
            email="other-admin@example.com",
            hashed_password="x",
            token_balance=1000,
            is_admin=True,
        )
        self.db.add(target_admin)
        self.db.commit()

        with self.assertRaises(AdminUserDeletionError):
            delete_user(self.db, target_admin.id)

        self.assertIsNotNone(self.db.query(User).filter(User.id == target_admin.id).first())

    def test_delete_user_removes_owned_rows_without_sqlite_fk_cascades(self) -> None:
        victim = User(
            id=2,
            email="victim@example.com",
            hashed_password="x",
            token_balance=1000,
        )
        self.db.add(victim)
        self.db.flush()
        self.db.add_all(
            [
                UserProfile(user_id=victim.id, persona_type="active"),
                Subscription(user_id=victim.id, ticker="MSFT"),
                ApiKey(
                    user_id=victim.id,
                    key_hash="victim-key-hash",
                    key_prefix="fd_live_v",
                    name="Victim key",
                ),
                Usage(
                    user_id=victim.id,
                    amount=-10,
                    balance_after=990,
                    transaction_type="analysis_cost",
                ),
                UserSchedule(
                    user_id=victim.id,
                    schedule_type="daily_digest",
                    enabled=True,
                    cron_expression="0 8 * * *",
                ),
                Execution(
                    id=43,
                    execution_type="ticker",
                    subject_type="ticker",
                    subject_id="MSFT",
                    creator_id=victim.id,
                    status="completed",
                    created_at=datetime(2026, 4, 8, 12, 0, 0),
                ),
            ]
        )
        self.db.flush()
        self.db.add_all(
            [
                Report(
                    id=12,
                    execution_id=43,
                    report_type="market_report",
                    content="Victim report",
                    created_at=datetime(2026, 4, 8, 12, 1, 0),
                ),
                ReportView(execution_id=43, viewer_id=1),
                ReportView(execution_id=42, viewer_id=victim.id),
            ]
        )
        session = ChatSession(user_id=victim.id, title="Victim chat")
        self.db.add(session)
        self.db.flush()
        session_id = session.id
        message = ChatMessage(
            session_id=session_id,
            role="user",
            content="hello",
            sort_order=1,
        )
        self.db.add(message)
        self.db.flush()
        self.db.add(
            ChatTurn(
                session_id=session.id,
                user_id=victim.id,
                status="completed",
                user_message_id=message.id,
            )
        )
        self.db.commit()

        self.assertTrue(delete_user(self.db, victim.id))

        self.assertIsNone(self.db.query(User).filter(User.id == victim.id).first())
        self.assertEqual(self.db.query(UserProfile).filter(UserProfile.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(Subscription).filter(Subscription.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(ApiKey).filter(ApiKey.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(Usage).filter(Usage.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(UserSchedule).filter(UserSchedule.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(ChatSession).filter(ChatSession.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count(), 0)
        self.assertEqual(self.db.query(ChatTurn).filter(ChatTurn.user_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(Execution).filter(Execution.creator_id == victim.id).count(), 0)
        self.assertEqual(self.db.query(Report).filter(Report.execution_id == 43).count(), 0)
        self.assertEqual(
            self.db.query(ReportView)
            .filter(
                (ReportView.viewer_id == victim.id)
                | (ReportView.execution_id == 43)
            )
            .count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()

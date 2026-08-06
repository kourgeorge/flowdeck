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
from models.db_models import Execution, Report, User
from services.admin_service import UserDeletionError, build_analysis_reports_zip, delete_user
from services.token_service import SYSTEM_USER_EMAIL


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
                    metadata_json=json.dumps({"score": 4, "source": "db"}),
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

    def test_delete_user_reassigns_owned_executions_to_system_user(self) -> None:
        self.db.add(User(id=2, email="creator@example.com", hashed_password="x", token_balance=500))
        self.db.add(
            Execution(
                id=43,
                execution_type="ticker",
                subject_type="ticker",
                subject_id="MSFT",
                creator_id=2,
                status="completed",
                created_at=datetime(2026, 4, 8, 12, 0, 0),
            )
        )
        self.db.add(
            Report(
                id=12,
                execution_id=43,
                report_type="market_report",
                content="Shared report should survive account deletion",
                metadata_json=None,
                created_at=datetime(2026, 4, 8, 12, 1, 0),
            )
        )
        self.db.commit()

        self.assertTrue(delete_user(self.db, 2))

        deleted_user = self.db.query(User).filter(User.id == 2).first()
        system_user = self.db.query(User).filter(User.email == SYSTEM_USER_EMAIL).one()
        preserved_execution = self.db.query(Execution).filter(Execution.id == 43).one()
        preserved_report = self.db.query(Report).filter(Report.id == 12).one()

        self.assertIsNone(deleted_user)
        self.assertEqual(preserved_execution.creator_id, system_user.id)
        self.assertEqual(preserved_report.execution_id, 43)

    def test_delete_user_blocks_admin_accounts(self) -> None:
        self.db.add(User(id=3, email="other-admin@example.com", hashed_password="x", is_admin=True))
        self.db.commit()

        with self.assertRaisesRegex(UserDeletionError, "Admin accounts"):
            delete_user(self.db, 3)

        self.assertIsNotNone(self.db.query(User).filter(User.id == 3).first())

    def test_delete_user_blocks_system_account(self) -> None:
        self.db.add(User(id=4, email=SYSTEM_USER_EMAIL, hashed_password=None, token_balance=0))
        self.db.commit()

        with self.assertRaisesRegex(UserDeletionError, "System account"):
            delete_user(self.db, 4)

        self.assertIsNotNone(self.db.query(User).filter(User.id == 4).first())


if __name__ == "__main__":
    unittest.main()

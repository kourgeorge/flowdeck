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

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, _set_sqlite_pragma_foreign_keys
from models.db_models import Execution, Report, User
from services.admin_service import build_analysis_reports_zip, delete_user


class TestAdminService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        event.listen(self.engine, "connect", _set_sqlite_pragma_foreign_keys)
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="admin@example.com", hashed_password="x", token_balance=1000))
        self.db.commit()
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
        self.db.commit()
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

    def test_delete_user_uses_sqlite_foreign_key_cascades(self) -> None:
        deleted = delete_user(self.db, 1)

        self.assertTrue(deleted)
        self.assertIsNone(self.db.query(User).filter(User.id == 1).first())
        self.assertEqual(self.db.query(Execution).filter(Execution.creator_id == 1).count(), 0)
        self.assertEqual(self.db.query(Report).filter(Report.execution_id == 42).count(), 0)


if __name__ == "__main__":
    unittest.main()

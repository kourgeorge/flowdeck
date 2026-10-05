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

from database import Base
from models.db_models import Execution, Report, Subscription, Usage, User
from services.admin_service import build_analysis_reports_zip, list_users
from services import token_service


class TestAdminUsers(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([
            User(id=1, email="first@example.com", created_at=datetime(2026, 10, 1)),
            User(id=2, email="second@example.com", created_at=datetime(2026, 10, 2)),
            User(id=3, email="new@example.com", created_at=datetime(2026, 10, 3)),
            User(id=4, email="system@example.com", token_balance=0, created_at=datetime(2026, 10, 4)),
        ])
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_users_have_independent_ledger_balances_and_subscription_counts(self) -> None:
        token_service.record_transaction(1, 1000, "initial_balance", self.db)
        token_service.record_transaction(1, -200, "analysis_cost", self.db)
        token_service.record_transaction(1, -2, "chat_cost", self.db, llm_tokens=20000)
        token_service.record_transaction(1, 200, "refund", self.db)
        token_service.record_transaction(1, 3, "view_reward", self.db)
        token_service.record_transaction(2, 1000, "initial_balance", self.db)
        token_service.record_transaction(2, -1000, "analysis_cost", self.db)
        self.db.add_all([
            Subscription(user_id=1, ticker="AAPL"),
            Subscription(user_id=1, ticker="MSFT"),
            Subscription(user_id=2, ticker="NVDA"),
        ])
        self.db.commit()

        items, total = list_users(self.db, limit=100, offset=0)
        by_id = {item["id"]: item for item in items}

        self.assertEqual(total, 4)
        self.assertEqual(by_id[1]["token_balance"], 1001)
        self.assertEqual(by_id[2]["token_balance"], 0)
        self.assertEqual(by_id[1]["token_balance"], token_service.get_balance(1, self.db))
        self.assertEqual(by_id[2]["token_balance"], token_service.get_balance(2, self.db))
        self.assertEqual(by_id[1]["subscription_count"], 2)
        self.assertEqual(by_id[2]["subscription_count"], 1)
        self.assertEqual(by_id[3]["subscription_count"], 0)
        # Transactions no longer update the old column.
        self.assertEqual(self.db.get(User, 1).token_balance, 1000)
        self.assertEqual(self.db.get(User, 2).token_balance, 1000)

    def test_uninitialized_users_keep_their_opening_balance_without_writes(self) -> None:
        items, _ = list_users(self.db, limit=100, offset=0)
        balances = {item["id"]: item["token_balance"] for item in items}

        self.assertEqual(balances, {1: 1000, 2: 1000, 3: 1000, 4: 0})
        self.assertEqual(self.db.query(Usage).count(), 0)

    def test_top_up_is_reflected_when_users_are_reloaded(self) -> None:
        token_service.record_transaction(1, 1000, "initial_balance", self.db)
        token_service.record_transaction(1, -200, "analysis_cost", self.db)
        items, _ = list_users(self.db, limit=100, offset=0)
        self.assertEqual(next(item for item in items if item["id"] == 1)["token_balance"], 800)

        self.assertTrue(token_service.top_up(1, 500, self.db))
        self.db.expire_all()
        items, _ = list_users(self.db, limit=100, offset=0)

        self.assertEqual(next(item for item in items if item["id"] == 1)["token_balance"], 1300)

    def test_pagination_keeps_balances_with_the_right_users_and_batches_queries(self) -> None:
        token_service.record_transaction(1, 120, "initial_balance", self.db)
        token_service.record_transaction(2, 340, "initial_balance", self.db)
        statements = []

        def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture_statement)
        try:
            items, total = list_users(self.db, limit=2, offset=2)
        finally:
            event.remove(self.engine, "before_cursor_execute", capture_statement)

        self.assertEqual(total, 4)
        self.assertEqual([(item["id"], item["token_balance"]) for item in items], [(2, 340), (1, 120)])
        self.assertEqual(len(statements), 4)
        self.assertEqual(list_users(self.db, limit=2, offset=4), ([], 4))


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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import User, UserSchedule
from services import scheduler


class TestScheduler(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        db = self.SessionLocal()
        db.add(
            User(
                id=1,
                email="briefs@example.com",
                hashed_password="x",
                token_balance=1000,
            )
        )
        db.add(
            UserSchedule(
                id=10,
                user_id=1,
                schedule_type="daily_digest",
                enabled=True,
                cron_expression="0 0 * * *",
                timezone="UTC",
            )
        )
        db.commit()
        db.close()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    async def test_failed_digest_does_not_mark_schedule_executed(self) -> None:
        with patch("services.scheduler.SessionLocal", self.SessionLocal), patch(
            "services.scheduler.run_and_store_digest",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = RuntimeError("digest failed")

            await scheduler.run_scheduled_jobs()

        db = self.SessionLocal()
        try:
            schedule = db.query(UserSchedule).filter(UserSchedule.id == 10).one()
            self.assertIsNone(schedule.last_executed_at)
        finally:
            db.close()
        mock_run.assert_awaited_once()

    async def test_successful_digest_marks_schedule_executed(self) -> None:
        with patch("services.scheduler.SessionLocal", self.SessionLocal), patch(
            "services.scheduler.run_and_store_digest",
            new_callable=AsyncMock,
        ) as mock_run, patch(
            "services.scheduler.send_daily_digest_email_to_user",
            return_value=True,
        ) as mock_send_email:
            mock_run.return_value = (object(), {}, 77, "2026-06-26")

            await scheduler.run_scheduled_jobs()

        db = self.SessionLocal()
        try:
            schedule = db.query(UserSchedule).filter(UserSchedule.id == 10).one()
            self.assertIsNotNone(schedule.last_executed_at)
        finally:
            db.close()
        mock_run.assert_awaited_once()
        mock_send_email.assert_called_once_with(77, "briefs@example.com")


if __name__ == "__main__":
    unittest.main()

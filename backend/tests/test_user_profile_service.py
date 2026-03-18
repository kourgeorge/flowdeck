from __future__ import annotations

from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import User, UserProfile
from services.user_profile_service import (
    build_user_context_snapshot,
    serialize_profile,
    update_profile,
)


class TestUserProfileService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="profile@example.com", hashed_password="x", token_balance=1200))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_update_profile_marks_onboarding_complete_when_required_fields_present(self) -> None:
        profile = update_profile(
            self.db,
            1,
            persona_type="investor",
            risk_tolerance="moderate",
            time_horizon="long_term",
            primary_goal="wealth_building",
            goals=["capital_growth", "capital_growth", "learning"],
            constraints=["avoid_leverage"],
            ai_memory_text="Avoid concentrated positions.",
        )

        serialized = serialize_profile(profile)

        self.assertTrue(serialized["has_completed_investor_profile"])
        self.assertEqual(serialized["goals"], ["capital_growth", "learning"])
        self.assertEqual(serialized["constraints"], ["avoid_leverage"])
        self.assertIsNotNone(serialized["onboarding_completed_at"])

    def test_build_user_context_snapshot_includes_memory_and_profile_fields(self) -> None:
        self.db.add(UserProfile(user_id=1, persona_type="trader", risk_tolerance="aggressive", ai_memory_text="Prefers event-driven setups."))
        self.db.commit()

        snapshot = build_user_context_snapshot(1, self.db)

        self.assertIn("Persona Type: trader", snapshot)
        self.assertIn("Risk Tolerance: aggressive", snapshot)
        self.assertIn("Prefers event-driven setups.", snapshot)


if __name__ == "__main__":
    unittest.main()

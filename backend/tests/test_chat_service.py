from __future__ import annotations

from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import User, UserProfile
from services.chat_service import _build_system_prompt


class TestChatServicePromptPersonalization(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="chat@example.com", hashed_password="x", token_balance=900))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_system_prompt_includes_saved_style_and_memory_instructions(self) -> None:
        self.db.add(
            UserProfile(
                user_id=1,
                persona_type="investor",
                experience_level="advanced",
                risk_tolerance="moderate",
                time_horizon="long_term",
                primary_goal="wealth_building",
                preferred_style="technical",
                ai_memory_text="Prefers valuation-driven entries and avoids leverage.",
            )
        )
        self.db.commit()

        prompt = _build_system_prompt(1, self.db, {"tickers": ["AAPL", "MSFT"]})

        self.assertIn("## Personalization Instructions", prompt)
        self.assertIn("Preferred AI Style: technical", prompt)
        self.assertIn("Use a more technical analytical style.", prompt)
        self.assertIn("Saved AI Memory: Prefers valuation-driven entries and avoids leverage.", prompt)
        self.assertIn("If the live request conflicts with saved preferences or memory, follow the live request", prompt)
        self.assertIn("default toward investment thesis, fundamentals, valuation", prompt)
        self.assertIn("User's Current Watchlist", prompt)

    def test_system_prompt_skips_personalization_when_profile_missing(self) -> None:
        prompt = _build_system_prompt(1, self.db, None)

        self.assertNotIn("## Personalization Instructions", prompt)
        self.assertNotIn("## Saved User Profile", prompt)


if __name__ == "__main__":
    unittest.main()

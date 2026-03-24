"""Test the update_user_memory tool."""

import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, User, UserProfile
from ai_engine.agent.tools.user_context import UpdateUserMemoryTool
from ai_engine.agent.tool import ExecutionContext


class TestUpdateUserMemoryTool(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Create test user
        self.user = User(
            id=1,
            email="test@example.com",
            name="Test User",
            created_at=datetime.utcnow(),
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_update_user_memory_creates_profile_if_not_exists(self) -> None:
        """Test that the tool creates a profile if it doesn't exist."""
        tool = UpdateUserMemoryTool(user_id=1, db=self.db)
        ctx = ExecutionContext(user_id=1, db=self.db)
        
        result = tool.execute(ctx, memory_note="I love tech sector")
        
        self.assertTrue(result.ok)
        self.assertIn("Saved to your AI memory", result.data)
        
        # Verify profile was created and memory was saved
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == 1).first()
        self.assertIsNotNone(profile)
        self.assertIn("I love tech sector", profile.ai_memory_text)

    def test_update_user_memory_appends_to_existing_memory(self) -> None:
        """Test that the tool appends to existing memory."""
        # Create profile with existing memory
        profile = UserProfile(
            user_id=1,
            ai_memory_text="[2026-01-01] Prefers value investing"
        )
        self.db.add(profile)
        self.db.commit()
        
        tool = UpdateUserMemoryTool(user_id=1, db=self.db)
        ctx = ExecutionContext(user_id=1, db=self.db)
        
        result = tool.execute(ctx, memory_note="I love tech sector")
        
        self.assertTrue(result.ok)
        
        # Verify memory was appended
        self.db.refresh(profile)
        self.assertIn("Prefers value investing", profile.ai_memory_text)
        self.assertIn("I love tech sector", profile.ai_memory_text)

    def test_update_user_memory_includes_timestamp(self) -> None:
        """Test that saved memory includes a timestamp."""
        tool = UpdateUserMemoryTool(user_id=1, db=self.db)
        ctx = ExecutionContext(user_id=1, db=self.db)
        
        result = tool.execute(ctx, memory_note="Risk-averse investor")
        
        self.assertTrue(result.ok)
        
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == 1).first()
        # Check for timestamp format [YYYY-MM-DD]
        self.assertRegex(profile.ai_memory_text, r"\[\d{4}-\d{2}-\d{2}\]")

    def test_update_user_memory_truncates_if_too_long(self) -> None:
        """Test that memory is truncated if it exceeds 4000 characters."""
        # Create profile with long existing memory
        long_memory = "x" * 3900
        profile = UserProfile(user_id=1, ai_memory_text=long_memory)
        self.db.add(profile)
        self.db.commit()
        
        tool = UpdateUserMemoryTool(user_id=1, db=self.db)
        ctx = ExecutionContext(user_id=1, db=self.db)
        
        result = tool.execute(ctx, memory_note="New important note")
        
        self.assertTrue(result.ok)
        
        self.db.refresh(profile)
        # Should be truncated to 4000 chars
        self.assertLessEqual(len(profile.ai_memory_text), 4000)
        # Should still contain the new note (kept from the end)
        self.assertIn("New important note", profile.ai_memory_text)

    def test_update_user_memory_handles_empty_note(self) -> None:
        """Test that empty memory notes are handled gracefully."""
        tool = UpdateUserMemoryTool(user_id=1, db=self.db)
        ctx = ExecutionContext(user_id=1, db=self.db)
        
        result = tool.execute(ctx, memory_note="")
        
        # Empty notes should return an error from the tool's execute method
        self.assertFalse(result.ok)
        self.assertEqual(result.error["code"], "MISSING_PARAM")


if __name__ == "__main__":
    unittest.main()

# Made with Bob

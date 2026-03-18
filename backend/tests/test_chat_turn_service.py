from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import ChatMessage, ChatSession, ChatTurn, User
from services.chat_turn_service import ChatTurnService


class _FakeChatService:
    def chat_stream(self, messages, user_id=None, db=None, context=None):
        yield 'data: {"type":"thinking","content":"Checking fundamentals"}\n\n'
        yield 'data: {"type":"token","content":"Hello"}\n\n'
        yield 'data: {"type":"token","content":" world"}\n\n'
        yield f'data: {json.dumps({"type": "done", "tokens_used": 12, "tools_called": 1, "follow_up_questions": ["Compare peers?"], "llm_usage": {"total_tokens": 12, "cost_usd": 0.02}})}\n\n'


class TestChatTurnService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.SessionLocal()
        db.add(User(id=1, email="chat@example.com", hashed_password="x", token_balance=500))
        db.commit()
        db.close()
        self.service = ChatTurnService()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_prepare_turn_persists_user_message_immediately(self) -> None:
        with patch("services.chat_turn_service.SessionLocal", self.SessionLocal):
            turn_id, session_id, messages = self.service.prepare_turn(
                user_id=1,
                body_messages=[{"role": "user", "content": "Compare MSFT and GOOGL"}],
                session_id=None,
            )

        db = self.SessionLocal()
        session = db.get(ChatSession, session_id)
        turn = db.get(ChatTurn, turn_id)
        saved_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.sort_order.asc()).all()

        self.assertIsNotNone(session)
        self.assertIsNotNone(turn)
        self.assertEqual(turn.status, "running")
        self.assertEqual(len(saved_messages), 1)
        self.assertEqual(saved_messages[0].role, "user")
        self.assertEqual(saved_messages[0].content, "Compare MSFT and GOOGL")
        self.assertEqual(messages[-1]["content"], "Compare MSFT and GOOGL")
        db.close()

    def test_run_turn_sync_completes_and_persists_assistant_reply(self) -> None:
        with patch("services.chat_turn_service.SessionLocal", self.SessionLocal):
            turn_id, session_id, messages = self.service.prepare_turn(
                user_id=1,
                body_messages=[{"role": "user", "content": "What is happening with NVDA?"}],
                session_id=None,
            )

            with patch("services.chat_turn_service.get_chat_service", return_value=_FakeChatService()):
                result = self.service.run_turn_sync(
                    turn_id=turn_id,
                    session_id=session_id,
                    user_id=1,
                    messages=messages,
                    context=None,
                )

        db = self.SessionLocal()
        turn = db.get(ChatTurn, turn_id)
        saved_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.sort_order.asc()).all()

        self.assertEqual(result["type"], "done")
        self.assertEqual(result["content"], "Hello world")
        self.assertEqual(turn.status, "completed")
        self.assertEqual(len(saved_messages), 2)
        self.assertEqual(saved_messages[1].role, "assistant")
        self.assertEqual(saved_messages[1].content, "Hello world")
        self.assertEqual(saved_messages[1].tools_called, 1)
        db.close()


if __name__ == "__main__":
    unittest.main()

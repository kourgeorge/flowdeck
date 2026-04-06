from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import ChatMessage, ChatSession, ChatTurn, Execution, Report, Usage, User
from services.token_service import llm_tokens_to_platform_tokens
from services.usage_service import get_user_usage_history


class TestTokenUsageService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()
        self.db.add(User(id=1, email="usage@example.com", hashed_password="x", token_balance=1000))
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_usage_history_combines_analysis_chat_and_digest(self) -> None:
        now = datetime.utcnow()

        analysis_execution = Execution(
            id=101,
            execution_type="ticker",
            subject_type="ticker",
            subject_id="AAPL",
            creator_id=1,
            status="completed",
            created_at=now - timedelta(days=3),
        )
        digest_execution = Execution(
            id=102,
            execution_type="daily_digest",
            subject_type="user_date",
            subject_id="1:w:2026-04-05",
            creator_id=1,
            status="completed",
            created_at=now - timedelta(days=2),
        )
        self.db.add_all([analysis_execution, digest_execution])
        self.db.flush()

        self.db.add_all(
            [
                Report(
                    execution_id=101,
                    report_type="final_trade_decision",
                    metadata_json=json.dumps(
                        {
                            "input_tokens": 900,
                            "output_tokens": 100,
                            "total_tokens": 1000,
                            "cost_usd": 1.25,
                        }
                    ),
                ),
                Report(
                    execution_id=102,
                    report_type="daily_digest",
                    metadata_json=json.dumps(
                        {
                            "input_tokens": 300,
                            "output_tokens": 50,
                            "total_tokens": 350,
                            "cost_usd": 0.42,
                        }
                    ),
                ),
            ]
        )

        self.db.add_all(
            [
                Usage(
                    user_id=1,
                    amount=-200,
                    balance_after=800,
                    transaction_type="analysis_cost",
                    related_entity_type="execution",
                    related_entity_id=101,
                    created_at=now - timedelta(days=3),
                ),
                Usage(
                    user_id=1,
                    amount=-20,
                    balance_after=780,
                    transaction_type="digest_cost",
                    related_entity_type="execution",
                    related_entity_id=102,
                    created_at=now - timedelta(days=2),
                ),
            ]
        )

        session = ChatSession(
            id=201,
            user_id=1,
            title="Should I buy NVDA now?",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        self.db.add(session)
        self.db.flush()

        assistant_message = ChatMessage(
            id=301,
            session_id=201,
            role="assistant",
            content="Here is the setup.",
            sort_order=1,
            tools_called=2,
            model_metadata_json=json.dumps(
                {
                    "input_tokens": 12000,
                    "output_tokens": 345,
                    "total_tokens": 12345,
                    "cost_usd": 0.18,
                }
            ),
            created_at=now - timedelta(days=1),
        )
        self.db.add(assistant_message)
        self.db.flush()

        platform_chat_tokens = llm_tokens_to_platform_tokens(12345)
        self.db.add(
            ChatTurn(
                id=401,
                session_id=201,
                user_id=1,
                status="completed",
                assistant_message_id=301,
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
            )
        )
        self.db.add(
            Usage(
                user_id=1,
                amount=-platform_chat_tokens,
                llm_tokens=12345,
                balance_after=780 - platform_chat_tokens,
                transaction_type="chat_cost",
                related_entity_type="chat_message",
                related_entity_id=301,
                created_at=now - timedelta(days=1),
            )
        )
        self.db.commit()

        payload = get_user_usage_history(self.db, 1, days=30, limit=10)

        self.assertEqual(payload["summary"]["analysis_count"], 1)
        self.assertEqual(payload["summary"]["digest_count"], 1)
        self.assertEqual(payload["summary"]["chat_count"], 1)
        self.assertEqual(payload["summary"]["analysis_platform_tokens"], 200)
        self.assertEqual(payload["summary"]["digest_platform_tokens"], 20)
        self.assertEqual(payload["summary"]["chat_platform_tokens"], platform_chat_tokens)
        self.assertEqual(payload["summary"]["analysis_llm_tokens"], 1000)
        self.assertEqual(payload["summary"]["digest_llm_tokens"], 350)
        self.assertEqual(payload["summary"]["chat_llm_tokens"], 12345)
        self.assertEqual(
            payload["summary"]["total_platform_tokens"],
            220 + platform_chat_tokens,
        )
        self.assertEqual(payload["returned_operations"], 3)

        self.assertEqual(payload["items"][0]["kind"], "chat")
        self.assertEqual(payload["items"][0]["chat_turn_id"], 401)
        self.assertEqual(payload["items"][0]["platform_tokens"], platform_chat_tokens)
        self.assertEqual(payload["items"][1]["kind"], "digest")
        self.assertEqual(payload["items"][1]["subject_label"], "2026-04-05")
        self.assertEqual(payload["items"][2]["kind"], "analysis")
        self.assertEqual(payload["items"][2]["subject_label"], "AAPL")

    def test_chat_operation_is_hidden_without_linked_usage_transaction(self) -> None:
        now = datetime.utcnow()

        session = ChatSession(
            id=501,
            user_id=1,
            title="Explain AMZN",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        message = ChatMessage(
            id=601,
            session_id=501,
            role="assistant",
            content="Analysis",
            sort_order=1,
            model_metadata_json=json.dumps(
                {
                    "input_tokens": 100,
                    "output_tokens": 25,
                    "total_tokens": 125,
                }
            ),
            created_at=now - timedelta(hours=2),
        )
        turn = ChatTurn(
            id=701,
            session_id=501,
            user_id=1,
            status="completed",
            assistant_message_id=601,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        self.db.add_all([session, message, turn])
        self.db.commit()

        payload = get_user_usage_history(self.db, 1, days=30, limit=10)

        self.assertEqual(payload["returned_operations"], 0)
        self.assertEqual(payload["summary"]["chat_count"], 0)


if __name__ == "__main__":
    unittest.main()

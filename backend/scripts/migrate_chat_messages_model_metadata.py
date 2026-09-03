#!/usr/bin/env python3
"""
Replace chat_messages.tokens_used with chat_messages.model_metadata_json.

Backfills model_metadata_json from tokens_used where set: {"total_tokens": N}.
Run from repo root: python backend/scripts/migrate_chat_messages_model_metadata.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text

from database import engine, init_db
from _migration_utils import table_has_column as _table_has_column


def main() -> None:
    init_db()

    with engine.connect() as conn:
        if _table_has_column(conn, "chat_messages", "tokens_used"):
            conn.execute(text("""
                CREATE TABLE chat_messages_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(32) NOT NULL,
                    content TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    model_metadata_json TEXT,
                    tools_called INTEGER,
                    tool_calls_json TEXT,
                    skill_events_json TEXT,
                    charts_json TEXT,
                    follow_up_questions_json TEXT,
                    created_at DATETIME NOT NULL
                )
            """))
            conn.execute(text("""
                INSERT INTO chat_messages_new (
                    id, session_id, role, content, sort_order, model_metadata_json,
                    tools_called, tool_calls_json, skill_events_json, charts_json,
                    follow_up_questions_json, created_at
                )
                SELECT
                    id, session_id, role, content, sort_order,
                    CASE WHEN tokens_used IS NOT NULL THEN json_object('total_tokens', tokens_used) ELSE NULL END,
                    tools_called, tool_calls_json, skill_events_json, charts_json,
                    follow_up_questions_json, created_at
                FROM chat_messages
            """))
            conn.execute(text("DROP TABLE chat_messages"))
            conn.execute(text("ALTER TABLE chat_messages_new RENAME TO chat_messages"))
            conn.execute(text("CREATE INDEX idx_chat_messages_session_id ON chat_messages (session_id)"))
            conn.commit()
            print("Replaced chat_messages.tokens_used with model_metadata_json")
        else:
            print("chat_messages already migrated (no tokens_used column)")

    print("Migration done.")


if __name__ == "__main__":
    main()

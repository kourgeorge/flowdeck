#!/usr/bin/env python3
"""
Add token economy schema to existing DB: users.token_balance, analysis_runs, report_views.
Run from repo root: python backend/scripts/migrate_token_economy.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from database import engine, init_db
from sqlalchemy import text
from models.db_models import Base, User, AnalysisRun, ReportView


def _users_has_column(conn, table: str, column: str) -> bool:
    """Return True if table has column (SQLite)."""
    r = conn.execute(text(f"PRAGMA table_info({table})"))
    for row in r:
        if row[1] == column:
            return True
    return False


def main() -> None:
    # Create new tables (analysis_runs, report_views) if they don't exist
    init_db()

    with engine.connect() as conn:
        # Add token_balance to users if missing
        if not _users_has_column(conn, "users", "token_balance"):
            conn.execute(text("ALTER TABLE users ADD COLUMN token_balance INTEGER NOT NULL DEFAULT 1000"))
            conn.commit()
            print("Added users.token_balance (default 1000)")
        else:
            print("users.token_balance already exists")

        # Add name to users if missing
        if not _users_has_column(conn, "users", "name"):
            conn.execute(text("ALTER TABLE users ADD COLUMN name VARCHAR(255)"))
            conn.commit()
            print("Added users.name")
        else:
            print("users.name already exists")

        # Backfill existing users that might have NULL token_balance
        try:
            conn.execute(text("UPDATE users SET token_balance = 1000 WHERE token_balance IS NULL"))
            conn.commit()
        except Exception:
            conn.rollback()
            pass

    print("Token economy migration done.")


if __name__ == "__main__":
    main()

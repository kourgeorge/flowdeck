#!/usr/bin/env python3
"""
Drop run_id from analysis_runs. Use analysis_runs.id as the canonical run identifier.
Run after deploying code that uses analysis_run_id for paths and API.
Run from repo root: python backend/scripts/migrate_drop_analysis_run_id.py
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
        if not _table_has_column(conn, "analysis_runs", "run_id"):
            print("analysis_runs.run_id already dropped")
            return

        conn.execute(text("""
            CREATE TABLE analysis_runs_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                ticker VARCHAR(32) NOT NULL,
                creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                earned_tokens INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("""
            INSERT INTO analysis_runs_new (id, ticker, creator_id, earned_tokens, created_at)
            SELECT id, ticker, creator_id, earned_tokens, created_at FROM analysis_runs
        """))
        conn.execute(text("DROP TABLE analysis_runs"))
        conn.execute(text("ALTER TABLE analysis_runs_new RENAME TO analysis_runs"))
        conn.execute(text("CREATE INDEX idx_analysis_runs_ticker ON analysis_runs (ticker)"))
        conn.commit()
        print("Dropped run_id from analysis_runs")

    print("Migration done.")


if __name__ == "__main__":
    main()

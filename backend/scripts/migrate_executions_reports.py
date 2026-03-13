#!/usr/bin/env python3
"""
Generalize runs and reports: create executions table, migrate from analysis_runs,
repoint reports and report_views to execution_id, drop analysis_runs.

Run from repo root: python backend/scripts/migrate_executions_reports.py
Safe to run multiple times (idempotent: skips if already migrated).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text

from database import engine, init_db


def _table_exists(conn, table: str) -> bool:
    r = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name={repr(table)}"))
    return r.fetchone() is not None


def _table_has_column(conn, table: str, column: str) -> bool:
    r = conn.execute(text(f"PRAGMA table_info({table})"))
    for row in r:
        if row[1] == column:
            return True
    return False


def main() -> None:
    init_db()

    with engine.connect() as conn:
        # Already migrated: executions exists and reports has execution_id
        if _table_exists(conn, "executions") and _table_has_column(conn, "reports", "execution_id"):
            print("Already migrated (executions exists, reports.execution_id present).")
            return

        # 1. Create executions table
        if not _table_exists(conn, "executions"):
            conn.execute(text("""
                CREATE TABLE executions (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    execution_type VARCHAR(64) NOT NULL,
                    subject_type VARCHAR(32) NOT NULL,
                    subject_id VARCHAR(255) NOT NULL,
                    creator_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    earned_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
            """))
            conn.execute(text("CREATE INDEX idx_executions_type_subject ON executions (execution_type, subject_type, subject_id)"))
            conn.execute(text("CREATE INDEX idx_executions_creator ON executions (creator_id)"))
            conn.commit()
            print("Created table executions")
        else:
            print("Table executions already exists")

        # 2. Migrate analysis_runs -> executions (preserve id for FK repoint)
        if _table_exists(conn, "analysis_runs"):
            conn.execute(text("""
                INSERT INTO executions (id, execution_type, subject_type, subject_id, creator_id, earned_tokens, created_at)
                SELECT id, 'ticker', 'ticker', ticker, creator_id, earned_tokens, created_at FROM analysis_runs
            """))
            conn.commit()
            print("Migrated analysis_runs -> executions")
        else:
            print("No analysis_runs table (already dropped or fresh install)")

        # 3. Reports: add execution_id, backfill, drop analysis_run_id and ticker
        if _table_has_column(conn, "reports", "analysis_run_id"):
            # SQLite: recreate reports without analysis_run_id and ticker
            conn.execute(text("""
                CREATE TABLE reports_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
                    report_type VARCHAR(64) NOT NULL,
                    content TEXT,
                    metadata_json TEXT,
                    created_at DATETIME NOT NULL,
                    UNIQUE (execution_id, report_type)
                )
            """))
            conn.execute(text("""
                INSERT INTO reports_new (id, execution_id, report_type, content, metadata_json, created_at)
                SELECT id, analysis_run_id, report_type, content, metadata_json, created_at FROM reports
            """))
            conn.execute(text("DROP TABLE reports"))
            conn.execute(text("ALTER TABLE reports_new RENAME TO reports"))
            conn.execute(text("CREATE INDEX idx_reports_execution_id ON reports (execution_id)"))
            conn.commit()
            print("Migrated reports to execution_id")
        elif not _table_has_column(conn, "reports", "execution_id"):
            raise RuntimeError("reports has neither analysis_run_id nor execution_id - unexpected schema")

        # 4. Report_views: add execution_id, drop analysis_run_id
        if _table_has_column(conn, "report_views", "analysis_run_id"):
            conn.execute(text("""
                CREATE TABLE report_views_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
                    viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    viewed_at DATETIME NOT NULL,
                    UNIQUE (execution_id, viewer_id)
                )
            """))
            conn.execute(text("""
                INSERT INTO report_views_new (id, execution_id, viewer_id, viewed_at)
                SELECT id, analysis_run_id, viewer_id, viewed_at FROM report_views
            """))
            conn.execute(text("DROP TABLE report_views"))
            conn.execute(text("ALTER TABLE report_views_new RENAME TO report_views"))
            conn.execute(text("CREATE INDEX idx_report_views_execution_id ON report_views (execution_id)"))
            conn.commit()
            print("Migrated report_views to execution_id")

        # 5. Drop analysis_runs
        if _table_exists(conn, "analysis_runs"):
            conn.execute(text("DROP TABLE analysis_runs"))
            conn.commit()
            print("Dropped table analysis_runs")

    print("Migration done.")


if __name__ == "__main__":
    main()

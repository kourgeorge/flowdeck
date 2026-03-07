#!/usr/bin/env python3
"""
Drop run_id from reports; drop run_id and ticker from report_views.
Run after deploying code that uses analysis_run_id + joins (Report/ReportView models no longer have run_id).
Run from repo root: python backend/scripts/migrate_drop_run_id_columns.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text

from database import engine, init_db


def _table_has_column(conn, table: str, column: str) -> bool:
    """Return True if table has column (SQLite)."""
    r = conn.execute(text(f"PRAGMA table_info({table})"))
    for row in r:
        if row[1] == column:
            return True
    return False


def main() -> None:
    init_db()

    with engine.connect() as conn:
        # SQLite 3.35+ supports DROP COLUMN. We recreate tables to also update unique constraints.

        if _table_has_column(conn, "reports", "run_id"):
            conn.execute(text("""
                CREATE TABLE reports_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    ticker VARCHAR(32) NOT NULL,
                    report_type VARCHAR(64) NOT NULL,
                    content TEXT,
                    metadata_json TEXT,
                    created_at DATETIME NOT NULL,
                    UNIQUE (analysis_run_id, report_type)
                )
            """))  # analysis_run_id nullable for legacy rows
            conn.execute(text("""
                INSERT INTO reports_new (id, analysis_run_id, ticker, report_type, content, metadata_json, created_at)
                SELECT id, analysis_run_id, ticker, report_type, content, metadata_json, created_at FROM reports
            """))
            conn.execute(text("DROP TABLE reports"))
            conn.execute(text("ALTER TABLE reports_new RENAME TO reports"))
            conn.execute(text("CREATE INDEX idx_reports_ticker ON reports (ticker)"))
            conn.execute(text("CREATE INDEX idx_reports_analysis_run_id ON reports (analysis_run_id)"))
            conn.commit()
            print("Dropped run_id from reports")
        else:
            print("reports.run_id already dropped")

        if _table_has_column(conn, "report_views", "run_id") or _table_has_column(conn, "report_views", "ticker"):
            conn.execute(text("""
                CREATE TABLE report_views_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER REFERENCES analysis_runs(id) ON DELETE CASCADE,
                    viewer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    viewed_at DATETIME NOT NULL,
                    UNIQUE (analysis_run_id, viewer_id)
                )
            """))
            conn.execute(text("""
                INSERT INTO report_views_new (id, analysis_run_id, viewer_id, viewed_at)
                SELECT id, analysis_run_id, viewer_id, viewed_at FROM report_views
            """))
            conn.execute(text("DROP TABLE report_views"))
            conn.execute(text("ALTER TABLE report_views_new RENAME TO report_views"))
            conn.execute(text("CREATE INDEX idx_report_views_analysis_run_id ON report_views (analysis_run_id)"))
            conn.commit()
            print("Dropped run_id and ticker from report_views")
        else:
            print("report_views already migrated")

    print("Migration done.")


if __name__ == "__main__":
    main()

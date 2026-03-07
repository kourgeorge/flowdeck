#!/usr/bin/env python3
"""
Add analysis_run_id FK to reports and report_views; backfill from analysis_runs by (ticker, run_id).
Creates AnalysisRun rows for orphan reports (e.g. from standalone or filesystem migration).
Run from repo root: python backend/scripts/migrate_report_analysis_run_fk.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text

from database import engine, init_db, SessionLocal
from models.db_models import Report, ReportView, AnalysisRun
from services import token_service


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
        if not _table_has_column(conn, "reports", "analysis_run_id"):
            conn.execute(text(
                "ALTER TABLE reports ADD COLUMN analysis_run_id INTEGER DEFAULT NULL "
                "REFERENCES analysis_runs(id) ON DELETE CASCADE"
            ))
            conn.commit()
            print("Added reports.analysis_run_id")
        else:
            print("reports.analysis_run_id already exists")

        if not _table_has_column(conn, "report_views", "analysis_run_id"):
            conn.execute(text(
                "ALTER TABLE report_views ADD COLUMN analysis_run_id INTEGER DEFAULT NULL "
                "REFERENCES analysis_runs(id) ON DELETE CASCADE"
            ))
            conn.commit()
            print("Added report_views.analysis_run_id")
        else:
            print("report_views.analysis_run_id already exists")

    db = SessionLocal()
    try:
        system_user_id = token_service.get_system_user_id(db)

        # Backfill reports
        reports_missing = db.query(Report).filter(Report.analysis_run_id.is_(None)).all()
        for r in reports_missing:
            ar = (
                db.query(AnalysisRun)
                .filter(AnalysisRun.ticker == r.ticker, AnalysisRun.run_id == r.run_id)
                .first()
            )
            if ar is None:
                ar = AnalysisRun(
                    ticker=r.ticker,
                    run_id=r.run_id,
                    creator_id=system_user_id,
                    earned_tokens=0,
                )
                db.add(ar)
                db.flush()
            r.analysis_run_id = ar.id
        if reports_missing:
            db.commit()
            print(f"Backfilled analysis_run_id for {len(reports_missing)} report(s)")
        else:
            print("No reports needed backfill")

        # Backfill report_views
        views_missing = db.query(ReportView).filter(ReportView.analysis_run_id.is_(None)).all()
        for v in views_missing:
            ar = (
                db.query(AnalysisRun)
                .filter(AnalysisRun.ticker == v.ticker, AnalysisRun.run_id == v.run_id)
                .first()
            )
            if ar is None:
                ar = AnalysisRun(
                    ticker=v.ticker,
                    run_id=v.run_id,
                    creator_id=system_user_id,
                    earned_tokens=0,
                )
                db.add(ar)
                db.flush()
            v.analysis_run_id = ar.id
        if views_missing:
            db.commit()
            print(f"Backfilled analysis_run_id for {len(views_missing)} report_view(s)")
        else:
            print("No report_views needed backfill")
    finally:
        db.close()

    print("Migration done.")


if __name__ == "__main__":
    main()

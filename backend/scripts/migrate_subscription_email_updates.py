#!/usr/bin/env python3
"""
Add email_updates column to subscriptions table.
Run from repo root: python backend/scripts/migrate_subscription_email_updates.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from database import engine, init_db
from sqlalchemy import text
from _migration_utils import table_has_column as _table_has_column


def main() -> None:
    init_db()

    with engine.connect() as conn:
        if not _table_has_column(conn, "subscriptions", "email_updates"):
            # SQLite: use INTEGER for boolean (0/1). Default 1 so existing subscribers keep getting emails.
            conn.execute(
                text("ALTER TABLE subscriptions ADD COLUMN email_updates INTEGER NOT NULL DEFAULT 1")
            )
            conn.commit()
            print("Added subscriptions.email_updates (default 1)")
        else:
            print("subscriptions.email_updates already exists")

    print("Subscription email_updates migration done.")


if __name__ == "__main__":
    main()

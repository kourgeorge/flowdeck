#!/usr/bin/env python3
"""
Add is_admin flag to users table. Optionally set admin by email via ADMIN_EMAIL env.
Run from repo root: python backend/scripts/migrate_admin_flag.py
Safe to run multiple times (idempotent).
"""

import os
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
        if not _table_has_column(conn, "users", "is_admin"):
            # SQLite: use INTEGER for boolean (0/1)
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
            print("Added users.is_admin (default 0)")
        else:
            print("users.is_admin already exists")

        admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            result = conn.execute(
                text("UPDATE users SET is_admin = 1 WHERE email = :email"),
                {"email": admin_email},
            )
            conn.commit()
            if result.rowcount and result.rowcount > 0:
                print(f"Set is_admin=1 for {admin_email}")
            else:
                print(f"No user found with email {admin_email} (ADMIN_EMAIL not applied)")

    print("Admin flag migration done.")


if __name__ == "__main__":
    main()

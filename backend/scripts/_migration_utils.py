"""Shared helpers for backend/scripts/migrate_*.py one-off migration scripts."""

from sqlalchemy import text


def table_has_column(conn, table: str, column: str) -> bool:
    """Return True if table has column (SQLite)."""
    r = conn.execute(text(f"PRAGMA table_info({table})"))
    for row in r:
        if row[1] == column:
            return True
    return False

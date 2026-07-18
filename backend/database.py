"""SQLite database configuration and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Default: flowdeck.db in backend directory
_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _BACKEND_DIR / "flowdeck.db"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{_DEFAULT_DB_PATH}",
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# SQLite-specific: allow multiple threads (analysis runs in background thread)
connect_args = {
    "check_same_thread": False,
} if _is_sqlite else {}

# Connection pool configuration to handle concurrent requests
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=os.environ.get("SQL_ECHO", "").lower() in ("true", "1", "yes"),
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _connection_record):
        """
        WAL mode: readers never block on writers and writers never block on readers.
        busy_timeout: instead of failing immediately on a locked DB, wait up to 5s.
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create all tables if they don't exist."""
    from models.db_models import (  # noqa: F401
        ApiKey,
        ChatMessage,
        ChatSession,
        ChatTurn,
        Execution,
        Report,
        ReportView,
        Subscription,
        User,
        UserProfile,
        UserSchedule,
    )
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

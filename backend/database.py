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

# SQLite-specific: allow multiple threads (analysis runs in background thread)
# Also add timeout to reduce "database is locked" errors
connect_args = {
    "check_same_thread": False,
    "timeout": 30.0,
} if DATABASE_URL.startswith("sqlite") else {}

# Connection pool configuration to handle concurrent requests
# For SQLite: pool_size limits concurrent connections, reducing lock contention
# For PostgreSQL/MySQL: standard pooling for performance
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_size=5,              # Number of connections to keep open
    max_overflow=10,          # Additional connections when pool is exhausted
    pool_pre_ping=True,       # Verify connections before using them
    pool_recycle=3600,        # Recycle connections after 1 hour
    echo=os.environ.get("SQL_ECHO", "").lower() in ("true", "1", "yes"),
)


def _set_sqlite_pragma_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enable SQLite foreign-key cascades for every pooled connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


if DATABASE_URL.startswith("sqlite"):
    event.listen(engine, "connect", _set_sqlite_pragma_foreign_keys)


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

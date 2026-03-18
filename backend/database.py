"""SQLite database configuration and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default: flowdeck.db in backend directory
_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _BACKEND_DIR / "flowdeck.db"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{_DEFAULT_DB_PATH}",
)

# SQLite-specific: allow multiple threads (analysis runs in background thread)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.environ.get("SQL_ECHO", "").lower() in ("true", "1", "yes"),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create all tables if they don't exist."""
    from models.db_models import (  # noqa: F401
        ApiKey,
        ChatMessage,
        ChatSession,
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

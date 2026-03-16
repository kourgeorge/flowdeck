"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
import secrets

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for Google OAuth users
    google_id = Column(String(255), nullable=True, unique=True, index=True)  # Google user ID
    token_balance = Column(Integer, nullable=False, default=1000)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")


class Execution(Base):
    """One row per AI run; subject is generic (execution_type, subject_type, subject_id)."""
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_type = Column(String(64), nullable=False, index=True)  # e.g. ticker, daily_digest
    subject_type = Column(String(32), nullable=False, index=True)  # e.g. ticker, user_date
    subject_id = Column(String(255), nullable=False, index=True)  # e.g. AAPL, 123:2025-03-13
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_executions_type_subject", "execution_type", "subject_type", "subject_id"),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type = Column(String(64), nullable=False)  # market_report, news_report, daily_digest, etc.
    content = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON: score, score_label, key_takeaways, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("execution_id", "report_type", name="uq_report_execution_type"),
        Index("idx_reports_execution_id", "execution_id"),
    )


class ReportView(Base):
    """Unique views per run per viewer; used for rewarding creators and enforcing uniqueness."""
    __tablename__ = "report_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    viewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("execution_id", "viewer_id", name="uq_report_view_execution_viewer"),
        Index("idx_report_views_execution_id", "execution_id"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    email_updates = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_subscription_user_ticker"),
    )


class ChatSession(Base):
    """One chat session per user; holds many messages."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # e.g. first user message snippet
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.sort_order")

    __table_args__ = (
        Index("idx_chat_sessions_user_updated", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    """One message in a chat session; assistant messages store token/tool metadata as JSON."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user | assistant
    content = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    model_metadata_json = Column(Text, nullable=True)  # JSON: provider, input_tokens, output_tokens, total_tokens, cost_usd, per_call
    tools_called = Column(Integer, nullable=True)
    tool_calls_json = Column(Text, nullable=True)  # JSON array of {name, input, output}
    skill_events_json = Column(Text, nullable=True)
    charts_json = Column(Text, nullable=True)
    follow_up_questions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index("idx_chat_messages_session_id", "session_id"),
    )


class ApiKey(Base):
    """API keys for programmatic access to FlowDeck."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)  # SHA256 hash of the key
    key_prefix = Column(String(16), nullable=False)  # First 8 chars for display (e.g., "fd_live_12345678")
    name = Column(String(255), nullable=False)  # User-friendly name (e.g., "Production Bot", "Dev Testing")
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration date

    __table_args__ = (
        Index("idx_api_keys_user_id", "user_id"),
        Index("idx_api_keys_key_hash", "key_hash"),
    )

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """
        Generate a new API key and its hash.
        
        Returns:
            tuple: (full_key, key_hash) where full_key is "fd_live_..." and key_hash is SHA256
        """
        import hashlib
        # Generate 32 random bytes (256 bits) for strong security
        key_secret = secrets.token_urlsafe(32)
        full_key = f"fd_live_{key_secret}"
        # Hash the full key for storage
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, key_hash

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for comparison."""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()


class UserSchedule(Base):
    """
    Generic scheduling configuration.

    One row represents a single scheduled job, which can be:
    - associated with a user (user_id not null), e.g. daily/weekly digest
    - global/system-level (user_id null), e.g. system maintenance tasks
    """

    __tablename__ = "user_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # When null, this schedule is system-level rather than per-user.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # Logical job type, e.g. "daily_digest", "weekly_digest"
    schedule_type = Column(String(64), nullable=False, index=True)

    # Whether this schedule is active. Disabled rows are ignored by the scheduler.
    enabled = Column(Boolean, nullable=False, default=True)

    # Precise time of day in the local timezone ("HH:MM" 24h format).
    # When null, the job can run at any time that other constraints allow.
    time_of_day = Column(String(8), nullable=True)

    # IANA timezone name, e.g. "Europe/Athens". When null, backend falls back to a default (e.g. UTC).
    timezone = Column(String(64), nullable=True)

    # Optional local weekday for weekly-style schedules: 0=Monday .. 6=Sunday (Python's weekday()).
    weekday = Column(Integer, nullable=True)

    # Arbitrary JSON payload for schedule-type-specific options (e.g. digest narrative_style, user_note, focus tickers).
    metadata_json = Column(Text, nullable=True)

    # Last time this schedule successfully executed (UTC).
    last_executed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # At most one row per (user, schedule_type) for now; can be relaxed later if needed.
        UniqueConstraint("user_id", "schedule_type", name="uq_user_schedule_user_type"),
        Index("idx_user_schedules_type_enabled", "schedule_type", "enabled"),
    )



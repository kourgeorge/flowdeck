"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, DateTime, Index, Boolean
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


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    ticker = Column(String(32), nullable=False, index=True)  # denormalized from analysis_runs for query convenience
    report_type = Column(String(64), nullable=False)  # market_report, news_report, etc.
    content = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON: score, score_label, key_takeaways, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("analysis_run_id", "report_type", name="uq_report_analysis_run_type"),
        Index("idx_reports_ticker", "ticker"),
        Index("idx_reports_analysis_run_id", "analysis_run_id"),
    )


class AnalysisRun(Base):
    """One analysis run per row; id is the canonical run identifier (used for paths, API, FKs)."""
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_analysis_runs_ticker", "ticker"),
    )


class ReportView(Base):
    """Unique views per run per viewer; used for rewarding creators and enforcing uniqueness."""
    __tablename__ = "report_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    viewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("analysis_run_id", "viewer_id", name="uq_report_view_analysis_run_viewer"),
        Index("idx_report_views_analysis_run_id", "analysis_run_id"),
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
    tokens_used = Column(Integer, nullable=True)
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



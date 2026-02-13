"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, DateTime, Index, Boolean
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    token_balance = Column(Integer, nullable=False, default=1000)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    run_id = Column(String(64), nullable=False)  # YYYY-MM-DD or YYYY-MM-DD_HH-MM-SS
    report_type = Column(String(64), nullable=False)  # market_report, news_report, etc.
    content = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON: score, score_label, key_takeaways, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "run_id", "report_type", name="uq_report_ticker_run_type"),
        Index("idx_reports_ticker_run", "ticker", "run_id"),
        Index("idx_reports_run_date", "run_id"),
    )


class AnalysisRun(Base):
    """Links a report run (ticker, run_id) to its creator for the token economy."""
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "run_id", name="uq_analysis_run_ticker_run"),
        Index("idx_analysis_runs_ticker_run", "ticker", "run_id"),
    )


class ReportView(Base):
    """Unique views per run per viewer; used for rewarding creators and enforcing uniqueness."""
    __tablename__ = "report_views"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    run_id = Column(String(64), nullable=False, index=True)
    viewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    viewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "run_id", "viewer_id", name="uq_report_view_ticker_run_viewer"),
        Index("idx_report_views_ticker_run", "ticker", "run_id"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_subscription_user_ticker"),
    )

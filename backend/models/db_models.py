"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint, DateTime, Index
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
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

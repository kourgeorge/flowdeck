"""Current user profile and stats. Routers delegate DB access here."""

from typing import Optional

from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from auth import hash_password, verify_password
from models.db_models import User, Execution, ReportView, Subscription


def get_profile(user: User, token_balance: int) -> dict:
    """Build profile dict for MeResponse from User and balance."""
    return {
        "user_id": user.id,
        "email": user.email,
        "name": getattr(user, "name", None) or None,
        "token_balance": token_balance,
        "is_admin": getattr(user, "is_admin", False),
        "has_password": user.hashed_password is not None,
    }


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Return user by id or None."""
    return db.query(User).filter(User.id == user_id).first()


def update_profile(
    db: Session,
    user_id: int,
    *,
    name: Optional[str] = None,
    current_password: Optional[str] = None,
    new_password: Optional[str] = None,
) -> User:
    """
    Update name and/or password. Validates current password if new_password provided.
    Returns updated user. Raises ValueError with message on validation failure.
    """
    user = get_user_by_id(db, user_id)
    if not user:
        raise ValueError("User not found")
    if new_password is not None:
        if not current_password:
            raise ValueError("Current password is required to set a new password")
        if not user.hashed_password or not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters")
        user.hashed_password = hash_password(new_password)
    if name is not None:
        user.name = (name or "").strip() or None
    db.commit()
    db.refresh(user)
    return user


def get_user_stats(db: Session, user_id: int) -> dict:
    """Return usage stats for the user (analyses_created, tokens_spent, etc.)."""
    analyses_created = (
        db.query(sqla_func.count(Execution.id))
        .filter(Execution.creator_id == user_id)
        .scalar() or 0
    )
    tokens_earned = (
        db.query(sqla_func.coalesce(sqla_func.sum(Execution.earned_tokens), 0))
        .filter(Execution.creator_id == user_id)
        .scalar() or 0
    )
    reports_viewed = (
        db.query(sqla_func.count(ReportView.id))
        .filter(ReportView.viewer_id == user_id)
        .scalar() or 0
    )
    unique_tickers = (
        db.query(sqla_func.count(sqla_func.distinct(Execution.subject_id)))
        .filter(
            Execution.creator_id == user_id,
            Execution.execution_type == "ticker",
        )
        .scalar() or 0
    )
    subscriptions_count = (
        db.query(sqla_func.count(Subscription.id))
        .filter(Subscription.user_id == user_id)
        .scalar() or 0
    )
    user = get_user_by_id(db, user_id)
    member_since = getattr(user, "created_at", None) if user else None
    member_since_str = member_since.strftime("%Y-%m-%d") if member_since else ""

    return {
        "analyses_created": int(analyses_created),
        "tokens_spent_on_analyses": int(analyses_created) * 200,
        "tokens_earned_from_views": int(tokens_earned),
        "reports_viewed": int(reports_viewed),
        "unique_tickers_analyzed": int(unique_tickers),
        "subscriptions_count": int(subscriptions_count),
        "member_since": member_since_str,
    }

"""Ticker subscription CRUD. Routers delegate all DB access here."""

from typing import List, Optional

from sqlalchemy.orm import Session

from models.db_models import Subscription


def list_for_user(db: Session, user_id: int) -> List[Subscription]:
    """List all subscriptions for the user."""
    return db.query(Subscription).filter(Subscription.user_id == user_id).all()


def subscribe(
    db: Session,
    user_id: int,
    ticker: str,
    email_updates: bool = True,
) -> tuple[Subscription, bool]:
    """
    Subscribe to a ticker. Returns (subscription, created).
    If already subscribed, returns existing subscription and created=False.
    """
    ticker_upper = ticker.strip().upper()
    existing = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id, Subscription.ticker == ticker_upper)
        .first()
    )
    if existing:
        return existing, False
    sub = Subscription(
        user_id=user_id,
        ticker=ticker_upper,
        email_updates=email_updates,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub, True


def get_by_ticker_for_user(
    db: Session, user_id: int, ticker: str
) -> Optional[Subscription]:
    """Return subscription if user is subscribed to the ticker."""
    ticker_upper = ticker.strip().upper()
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.ticker == ticker_upper,
        )
        .first()
    )


def update_email_updates(
    db: Session, user_id: int, ticker: str, email_updates: bool
) -> Subscription:
    """Update email_updates for a subscription. Raises ValueError if not found."""
    sub = get_by_ticker_for_user(db, user_id, ticker)
    if not sub:
        raise ValueError("Subscription not found")
    sub.email_updates = email_updates
    db.commit()
    db.refresh(sub)
    return sub


def unsubscribe(db: Session, user_id: int, ticker: str) -> bool:
    """Remove subscription if it exists. Returns True if removed."""
    sub = get_by_ticker_for_user(db, user_id, ticker)
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True

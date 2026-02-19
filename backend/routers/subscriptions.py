"""Ticker subscription endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User, Subscription
from auth import get_current_user
from services.email_service import notify_admin_new_subscription, send_subscription_confirmation

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class SubscribeRequest(BaseModel):
    ticker: str
    email_updates: bool = True


class SubscriptionResponse(BaseModel):
    id: int
    ticker: str
    email_updates: bool
    created_at: str


class PatchSubscriptionRequest(BaseModel):
    email_updates: bool


class SubscriptionsListResponse(BaseModel):
    subscriptions: list[SubscriptionResponse]


@router.get("", response_model=SubscriptionsListResponse)
def list_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tickers the current user is subscribed to."""
    rows = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    return SubscriptionsListResponse(
        subscriptions=[
            SubscriptionResponse(
                id=s.id,
                ticker=s.ticker,
                email_updates=getattr(s, "email_updates", True),
                created_at=s.created_at.isoformat(),
            )
            for s in rows
        ]
    )


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def subscribe(
    req: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe to a ticker."""
    ticker = (req.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    existing = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id, Subscription.ticker == ticker)
        .first()
    )
    if existing:
        return SubscriptionResponse(
            id=existing.id,
            ticker=existing.ticker,
            email_updates=getattr(existing, "email_updates", True),
            created_at=existing.created_at.isoformat(),
        )
    sub = Subscription(
        user_id=current_user.id,
        ticker=ticker,
        email_updates=req.email_updates,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    # Notify admin and send user a confirmation email (best-effort; do not fail the request)
    try:
        notify_admin_new_subscription(
            user_email=current_user.email or "(no email)",
            ticker=ticker,
        )
    except Exception:
        pass
    try:
        if current_user.email:
            send_subscription_confirmation(user_email=current_user.email, ticker=ticker)
    except Exception:
        pass
    return SubscriptionResponse(
        id=sub.id,
        ticker=sub.ticker,
        email_updates=sub.email_updates,
        created_at=sub.created_at.isoformat(),
    )


@router.patch("/{ticker}", response_model=SubscriptionResponse)
def update_subscription(
    ticker: str,
    req: PatchSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update email_updates preference for a subscription."""
    ticker_upper = ticker.strip().upper()
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.ticker == ticker_upper,
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.email_updates = req.email_updates
    db.commit()
    db.refresh(sub)
    return SubscriptionResponse(
        id=sub.id,
        ticker=sub.ticker,
        email_updates=sub.email_updates,
        created_at=sub.created_at.isoformat(),
    )


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unsubscribe from a ticker."""
    ticker_upper = ticker.strip().upper()
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.ticker == ticker_upper,
        )
        .first()
    )
    if sub:
        db.delete(sub)
        db.commit()

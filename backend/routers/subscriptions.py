"""Ticker subscription endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User
from services.email_service import notify_admin_new_subscription, send_subscription_confirmation
from services import subscription_service

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


def _sub_to_response(s) -> SubscriptionResponse:
    return SubscriptionResponse(
        id=s.id,
        ticker=s.ticker,
        email_updates=getattr(s, "email_updates", True),
        created_at=s.created_at.isoformat(),
    )


@router.get("", response_model=SubscriptionsListResponse)
def list_subscriptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tickers the current user is subscribed to."""
    rows = subscription_service.list_for_user(db, current_user.id)
    return SubscriptionsListResponse(
        subscriptions=[_sub_to_response(s) for s in rows]
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
    sub, created = subscription_service.subscribe(
        db, current_user.id, ticker, email_updates=req.email_updates
    )
    if created:
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
    return _sub_to_response(sub)


@router.patch("/{ticker}", response_model=SubscriptionResponse)
def update_subscription(
    ticker: str,
    req: PatchSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update email_updates preference for a subscription."""
    try:
        sub = subscription_service.update_email_updates(
            db, current_user.id, ticker, req.email_updates
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return _sub_to_response(sub)


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unsubscribe from a ticker."""
    subscription_service.unsubscribe(db, current_user.id, ticker)

"""API key CRUD. Routers delegate all DB access here."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from models.db_models import ApiKey


class ApiKeyNotFoundError(Exception):
    """API key not found or not owned by user."""


def create(
    db: Session,
    user_id: int,
    name: str,
    expires_at: Optional[datetime] = None,
) -> tuple[ApiKey, str]:
    """
    Create a new API key. Returns (api_key_entity, full_key).
    Caller must not store full_key; it is only shown once.
    """
    full_key, key_hash = ApiKey.generate_key()
    key_prefix = full_key[:16]
    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name.strip(),
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, full_key


def list_by_user(db: Session, user_id: int) -> List[ApiKey]:
    """List all API keys for the user, newest first."""
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def get_by_id_for_user(db: Session, key_id: int, user_id: int) -> Optional[ApiKey]:
    """Return the API key if it exists and belongs to the user."""
    return (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.user_id == user_id)
        .first()
    )


def delete(db: Session, key_id: int, user_id: int) -> None:
    """Delete an API key. Raises ApiKeyNotFoundError if not found."""
    api_key = get_by_id_for_user(db, key_id, user_id)
    if not api_key:
        raise ApiKeyNotFoundError("API key not found")
    db.delete(api_key)
    db.commit()


def set_active(db: Session, key_id: int, user_id: int, active: bool) -> ApiKey:
    """Deactivate or activate an API key. Raises ApiKeyNotFoundError if not found."""
    api_key = get_by_id_for_user(db, key_id, user_id)
    if not api_key:
        raise ApiKeyNotFoundError("API key not found")
    api_key.is_active = active
    db.commit()
    db.refresh(api_key)
    return api_key

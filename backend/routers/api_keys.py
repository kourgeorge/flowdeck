"""API Key management endpoints."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User
from services import api_key_service

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


class CreateApiKeyRequest(BaseModel):
    name: str
    expires_at: Optional[str] = None  # ISO 8601 datetime string


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: str
    last_used_at: Optional[str]
    expires_at: Optional[str]


class CreateApiKeyResponse(BaseModel):
    id: int
    name: str
    key: str  # Full key - only shown once!
    key_prefix: str
    is_active: bool
    created_at: str
    expires_at: Optional[str]
    warning: str = "Save this key now - it won't be shown again!"


def _api_key_to_response(key) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        is_active=key.is_active,
        created_at=key.created_at.isoformat(),
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
    )


@router.post("", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new API key for programmatic access.
    
    The full key is only returned once - save it securely!
    API keys can be used instead of JWT tokens by passing them in the Authorization header:
    `Authorization: Bearer fd_live_...`
    """
    if not req.name or len(req.name.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key name is required"
        )
    if len(req.name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key name must be 255 characters or less"
        )
    expires_at = None
    if req.expires_at:
        try:
            expires_at = datetime.fromisoformat(req.expires_at.replace('Z', '+00:00'))
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Expiration date must be in the future"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expiration date format. Use ISO 8601 (e.g., '2026-12-31T23:59:59Z')"
            )
    api_key, full_key = api_key_service.create(
        db, current_user.id, req.name.strip(), expires_at=expires_at
    )
    return CreateApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=full_key,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )


@router.get("", response_model=List[ApiKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = api_key_service.list_by_user(db, current_user.id)
    return [_api_key_to_response(key) for key in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an API key. This action is irreversible."""
    try:
        api_key_service.delete(db, key_id, current_user.id)
    except api_key_service.ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return None


@router.patch("/{key_id}/deactivate", response_model=ApiKeyResponse)
def deactivate_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate an API key without deleting it. Can be reactivated later."""
    try:
        api_key = api_key_service.set_active(db, key_id, current_user.id, False)
    except api_key_service.ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return _api_key_to_response(api_key)


@router.patch("/{key_id}/activate", response_model=ApiKeyResponse)
def activate_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reactivate a deactivated API key."""
    try:
        api_key = api_key_service.set_active(db, key_id, current_user.id, True)
    except api_key_service.ApiKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    return _api_key_to_response(api_key)



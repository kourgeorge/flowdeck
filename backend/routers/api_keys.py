"""API Key management endpoints."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import ApiKey, User

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
    # Validate name
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
    
    # Parse expiration date if provided
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
    
    # Generate the API key
    full_key, key_hash = ApiKey.generate_key()
    key_prefix = full_key[:16]  # "fd_live_" + first 8 chars of secret
    
    # Create database record
    api_key = ApiKey(
        user_id=current_user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=req.name.strip(),
        is_active=True,
        expires_at=expires_at,
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
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
    keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).order_by(ApiKey.created_at.desc()).all()
    
    return [
        ApiKeyResponse(
            id=key.id,
            name=key.name,
            key_prefix=key.key_prefix,
            is_active=key.is_active,
            created_at=key.created_at.isoformat(),
            last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
            expires_at=key.expires_at.isoformat() if key.expires_at else None,
        )
        for key in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an API key. This action is irreversible."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    db.delete(api_key)
    db.commit()
    return None


@router.patch("/{key_id}/deactivate", response_model=ApiKeyResponse)
def deactivate_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate an API key without deleting it. Can be reactivated later."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )


@router.patch("/{key_id}/activate", response_model=ApiKeyResponse)
def activate_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reactivate a deactivated API key."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    api_key.is_active = True
    db.commit()
    db.refresh(api_key)
    
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        last_used_at=api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
    )



"""JWT authentication utilities."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User

# Secret for JWT signing. In production, use a strong env var.
JWT_SECRET = os.environ.get("JWT_SECRET", "flowdeck-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return current user if valid token or API key, else None. Use for optional auth."""
    if not credentials or not credentials.credentials:
        return None
    
    token = credentials.credentials
    
    # Check if it's an API key (starts with "fd_live_")
    if token.startswith("fd_live_"):
        from models.db_models import ApiKey
        from datetime import datetime, timezone
        
        key_hash = ApiKey.hash_key(token)
        api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        
        if not api_key:
            return None
        
        # Check if key is active
        if not api_key.is_active:
            return None
        
        # Check if key has expired
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None
        
        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
        
        # Return the user associated with this API key
        return db.query(User).filter(User.id == api_key.user_id).first()
    
    # Otherwise, treat as JWT token
    sub = decode_token(token)
    if not sub:
        return None
    try:
        user_id = int(sub)
    except ValueError:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Return current user or raise 401. Use for protected endpoints."""
    user = get_current_user_optional(credentials, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return current user if admin, else raise 403. Use for admin-only endpoints."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user

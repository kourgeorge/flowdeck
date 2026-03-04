"""User registration and login."""

import os
import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from database import get_db
from models.db_models import User
from services.email_service import send_welcome_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DeleteAccountRequest(BaseModel):
    password: Optional[str] = None  # Optional for Google-only users


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        token_balance=1000,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        send_welcome_email(user.email)
    except Exception:
        pass  # Don't fail registration if welcome email fails
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login and return JWT token."""
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user_id=user.id, email=user.email)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    req: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the current user's account. Requires password confirmation for password users. Irreversible."""
    # If user has a password (email/password user), require password confirmation
    if current_user.hashed_password:
        if not req.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required for account deletion",
            )
        if not verify_password(req.password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )
    # Google-only users (no password) can delete without password confirmation
    # They're already authenticated via JWT token
    
    db.delete(current_user)
    db.commit()
    return None


@router.get("/google")
def google_login():
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    
    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Build Google OAuth URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    
    try:
        # Exchange authorization code for tokens
        import requests as http_requests
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        
        token_response = http_requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Verify and decode the ID token
        id_info = id_token.verify_oauth2_token(
            tokens["id_token"],
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        
        # Extract user info
        google_user_id = id_info["sub"]
        email = id_info.get("email", "").lower()
        name = id_info.get("name")
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google",
            )
        
        # Find or create user
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            # Update existing user with Google ID if not set
            if not user.google_id:
                user.google_id = google_user_id
                db.commit()
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                google_id=google_user_id,
                hashed_password=None,  # No password for Google users
                token_balance=1000,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Send welcome email
            try:
                send_welcome_email(email)
            except Exception:
                pass  # Don't fail login if welcome email fails
        
        # Generate JWT token
        jwt_token = create_access_token(str(user.id))
        
        # Redirect to frontend with token
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}&email={email}&user_id={user.id}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        # Redirect to frontend with error
        error_msg = str(e)
        redirect_url = f"{FRONTEND_URL}/auth/callback?error={error_msg}"
        return RedirectResponse(url=redirect_url)

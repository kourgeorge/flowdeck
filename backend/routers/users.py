"""User registration and login."""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User, OAuthState
from services.auth_service import (
    AuthError,
    delete_account as auth_delete_account,
    get_google_auth_url,
    google_callback as auth_google_callback,
    login as auth_login,
    register as auth_register,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

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
    password: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


def _auth_error_to_http(e: AuthError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        token, user_id, email = auth_register(req.email, req.password, db)
        return TokenResponse(access_token=token, user_id=user_id, email=email)
    except AuthError as e:
        raise _auth_error_to_http(e)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login and return JWT token."""
    try:
        token, user_id, email = auth_login(req.email, req.password, db)
        return TokenResponse(access_token=token, user_id=user_id, email=email)
    except AuthError as e:
        raise _auth_error_to_http(e)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    req: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the current user's account. Requires password for password users. Irreversible."""
    try:
        auth_delete_account(current_user, req.password, db)
        return None
    except AuthError as e:
        raise _auth_error_to_http(e)


@router.get("/google")
def google_login(request: Request, db: Session = Depends(get_db)):
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    nonce = secrets.token_urlsafe(32)
    db.query(OAuthState).filter(OAuthState.expires_at < datetime.utcnow()).delete()
    db.add(OAuthState(nonce_hash=hashlib.sha256(nonce.encode()).hexdigest(),
                      expires_at=datetime.utcnow() + timedelta(minutes=10)))
    db.commit()
    response = RedirectResponse(url=get_google_auth_url(GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, nonce))
    secure = GOOGLE_REDIRECT_URI.startswith("https://")
    response.set_cookie(_oauth_cookie_name(), nonce, max_age=600, httponly=True,
                        secure=secure, samesite="lax", path="/")
    return response


def _oauth_cookie_name():
    return "__Host-flowdeck-oauth-state" if GOOGLE_REDIRECT_URI.startswith("https://") else "flowdeck-oauth-state"


@router.get("/google/callback")
def google_callback_route(request: Request, code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    try:
        cookie = request.cookies.get(_oauth_cookie_name())
        if not state or not cookie or not secrets.compare_digest(state, cookie):
            raise AuthError(400, "Invalid OAuth state")
        consumed = db.query(OAuthState).filter(
            OAuthState.nonce_hash == hashlib.sha256(state.encode()).hexdigest(),
            OAuthState.expires_at > datetime.utcnow(),
        ).delete()
        db.commit()
        if consumed != 1:
            raise AuthError(400, "Expired or reused OAuth state")
        user, jwt_token, is_new_user = auth_google_callback(
            code,
            db,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        is_new_flag = "1" if is_new_user else "0"
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}&email={user.email}&user_id={user.id}&is_new={is_new_flag}"
        response = RedirectResponse(url=redirect_url)
        response.delete_cookie(_oauth_cookie_name(), path="/")
        return response
    except AuthError as e:
        redirect_url = f"{FRONTEND_URL}/auth/callback?error={e.detail}"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        redirect_url = f"{FRONTEND_URL}/auth/callback?error={str(e)}"
        return RedirectResponse(url=redirect_url)

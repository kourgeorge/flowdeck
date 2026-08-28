"""User registration and login."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User
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
def google_login():
    """Initiate Google OAuth flow."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured",
        )
    auth_url = get_google_auth_url(GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI)
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
def google_callback_route(code: str, state: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    try:
        user, jwt_token, is_new_user = auth_google_callback(
            code,
            db,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=GOOGLE_REDIRECT_URI,
        )
        is_new_flag = "1" if is_new_user else "0"
        redirect_url = f"{FRONTEND_URL}/auth/callback?token={jwt_token}&email={user.email}&user_id={user.id}&is_new={is_new_flag}"
        return RedirectResponse(url=redirect_url)
    except AuthError as e:
        redirect_url = f"{FRONTEND_URL}/auth/callback?error={e.detail}"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        redirect_url = f"{FRONTEND_URL}/auth/callback?error={str(e)}"
        return RedirectResponse(url=redirect_url)

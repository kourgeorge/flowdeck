"""
Auth business logic: registration, login, account deletion, Google OAuth.
Routers call this service and map results/exceptions to HTTP responses.
"""

import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from auth import create_access_token, hash_password, verify_password
from config import MAJOR_TICKERS
from models.db_models import User
from services.email_service import send_welcome_email
from services.subscription_service import subscribe_many
from services.user_profile_service import ensure_profile_exists


class AuthError(Exception):
    """Raised for auth failures; router maps to HTTPException(status_code, detail)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# Default token balance for new users
DEFAULT_TOKEN_BALANCE = 1000

# Min password length for registration
MIN_PASSWORD_LENGTH = 6


DEFAULT_SIGNUP_TICKERS = tuple(MAJOR_TICKERS)


def register(email: str, password: str, db: Session) -> Tuple[str, int, str]:
    """
    Register a new user. Returns (access_token, user_id, email).
    Raises AuthError(400, ...) for validation, AuthError(409, ...) if email already registered.
    """
    email = email.strip().lower()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(400, "Password must be at least 6 characters")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise AuthError(409, "Email already registered")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        token_balance=DEFAULT_TOKEN_BALANCE,
    )
    db.add(user)
    db.flush()
    ensure_profile_exists(db, user.id)
    subscribe_many(
        db,
        user.id,
        DEFAULT_SIGNUP_TICKERS,
        email_updates=False,
    )
    db.commit()
    db.refresh(user)
    try:
        send_welcome_email(user.email)
    except Exception:
        pass
    token = create_access_token(str(user.id))
    return token, user.id, user.email


def login(email: str, password: str, db: Session) -> Tuple[str, int, str]:
    """
    Authenticate user. Returns (access_token, user_id, email).
    Raises AuthError(401, "Invalid email or password") on failure.
    """
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise AuthError(401, "Invalid email or password")
    token = create_access_token(str(user.id))
    return token, user.id, user.email


def delete_account(user: User, password: Optional[str], db: Session) -> None:
    """
    Delete the current user's account. Irreversible.
    For password users, password must be provided and correct.
    Raises AuthError(400, ...) or AuthError(401, ...) on validation failure.
    """
    if user.hashed_password:
        if not password:
            raise AuthError(400, "Password required for account deletion")
        if not verify_password(password, user.hashed_password):
            raise AuthError(401, "Invalid password")
    db.delete(user)
    db.commit()


def get_google_auth_url(client_id: str, redirect_uri: str, state: Optional[str] = None) -> str:
    """Build Google OAuth 2.0 authorization URL. state is generated if not provided."""
    if not state:
        state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def google_callback(
    code: str,
    db: Session,
    *,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
 ) -> Tuple[User, str, bool]:
    """
    Exchange Google OAuth code for user and JWT. Returns (user, access_token, is_new_user).
    Creates user if first Google login. Sends welcome email for new users (best effort).
    Raises AuthError on configuration or token/email failure.
    """
    if not client_id or not client_secret or not redirect_uri:
        raise AuthError(500, "Google OAuth not configured")

    import requests as http_requests
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    token_response = http_requests.post(token_url, data=token_data)
    token_response.raise_for_status()
    tokens = token_response.json()
    id_token_jwt = tokens.get("id_token")
    if not id_token_jwt:
        raise AuthError(400, "Google did not return an ID token")

    id_info = id_token.verify_oauth2_token(
        id_token_jwt,
        google_requests.Request(),
        client_id,
        clock_skew_in_seconds=10,
    )
    google_user_id = id_info["sub"]
    email = (id_info.get("email") or "").strip().lower()
    name = id_info.get("name")
    if not email:
        raise AuthError(400, "Email not provided by Google")

    user = db.query(User).filter(User.email == email).first()
    is_new_user = False
    if user:
        if not user.google_id:
            user.google_id = google_user_id
            db.commit()
            db.refresh(user)
    else:
        is_new_user = True
        user = User(
            email=email,
            name=name,
            google_id=google_user_id,
            hashed_password=None,
            token_balance=DEFAULT_TOKEN_BALANCE,
        )
        db.add(user)
        db.flush()
        ensure_profile_exists(db, user.id)
        subscribe_many(
            db,
            user.id,
            DEFAULT_SIGNUP_TICKERS,
            email_updates=False,
        )
        db.commit()
        db.refresh(user)
        try:
            send_welcome_email(email)
        except Exception:
            pass

    token = create_access_token(str(user.id))
    return user, token, is_new_user

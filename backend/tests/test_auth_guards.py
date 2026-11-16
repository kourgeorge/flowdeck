"""Guards that stop account takeover: Google identity checks, duplicate email,
wrong-password rejection on login, password change and account deletion.

Each of these was verified by hand before; these tests make sure a refactor
can't quietly drop one of them.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import User
from services.auth_service import AuthError, delete_account, google_callback, login, register
from services.me_service import update_profile


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def no_welcome_email():
    with patch("services.auth_service.send_welcome_email"):
        yield


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _fake_google_modules(id_info: dict) -> dict:
    """Stand-ins for requests and google-auth so no network call is made and
    the ID token "says" whatever the test needs."""
    fake_requests = types.ModuleType("requests")
    fake_requests.post = lambda *args, **kwargs: _FakeResponse({"id_token": "fake-jwt"})

    fake_google_requests = types.ModuleType("google.auth.transport.requests")
    fake_google_requests.Request = type("_Request", (), {})

    fake_id_token = types.ModuleType("google.oauth2.id_token")
    fake_id_token.verify_oauth2_token = lambda *args, **kwargs: dict(id_info)

    return {
        "requests": fake_requests,
        "google": types.ModuleType("google"),
        "google.auth": types.ModuleType("google.auth"),
        "google.auth.transport": types.ModuleType("google.auth.transport"),
        "google.auth.transport.requests": fake_google_requests,
        "google.oauth2": types.ModuleType("google.oauth2"),
        "google.oauth2.id_token": fake_id_token,
    }


def _google_login(db, id_info: dict):
    with patch.dict(sys.modules, _fake_google_modules(id_info)):
        return google_callback(
            "oauth-code",
            db,
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="https://example.com/callback",
        )


def _user(db, email: str) -> User | None:
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


# --- Google OAuth -----------------------------------------------------------


def test_google_unverified_email_cannot_link_to_existing_password_account(db):
    register("victim@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        _google_login(
            db,
            {"sub": "attacker-sub", "email": "victim@x.com", "email_verified": False},
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Google email is not verified"
    assert _user(db, "victim@x.com").google_id is None


def test_google_missing_email_verified_flag_is_treated_as_unverified(db):
    register("victim@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        _google_login(db, {"sub": "attacker-sub", "email": "victim@x.com"})

    assert exc.value.status_code == 400
    assert _user(db, "victim@x.com").google_id is None


def test_google_different_identity_for_linked_email_is_rejected(db):
    _google_login(db, {"sub": "g1", "email": "v@x.com", "email_verified": True})

    with pytest.raises(AuthError) as exc:
        _google_login(db, {"sub": "g2", "email": "V@x.com", "email_verified": True})

    assert exc.value.status_code == 409
    assert exc.value.detail == "Google identity does not match this account"
    assert _user(db, "v@x.com").google_id == "g1"


# --- Registration -----------------------------------------------------------


def test_register_duplicate_email_ignores_case_and_spaces(db):
    register("a@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        register(" A@X.com ", "other-pass", db)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Email already registered"
    assert db.query(User).count() == 1


# --- Login ------------------------------------------------------------------


def test_login_wrong_password_is_401(db):
    register("a@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        login("a@x.com", "wrong-pass", db)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"


def test_login_unknown_email_is_401_with_same_message(db):
    register("a@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        login("nobody@x.com", "secret123", db)

    # Same message as a wrong password, so login can't be used to probe
    # which emails have accounts.
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"


def test_login_google_only_account_rejects_any_password(db):
    _google_login(db, {"sub": "g1", "email": "g@x.com", "email_verified": True})

    with pytest.raises(AuthError) as exc:
        login("g@x.com", "anything", db)

    assert exc.value.status_code == 401


# --- Password change --------------------------------------------------------


def test_update_profile_wrong_current_password_is_rejected(db):
    _, user_id, _ = register("a@x.com", "secret123", db)

    with pytest.raises(ValueError, match="Current password is incorrect"):
        update_profile(db, user_id, current_password="wrong-pass", new_password="newpass123")

    login("a@x.com", "secret123", db)


def test_update_profile_missing_current_password_is_rejected(db):
    _, user_id, _ = register("a@x.com", "secret123", db)

    with pytest.raises(ValueError, match="Current password is required"):
        update_profile(db, user_id, new_password="newpass123")
    with pytest.raises(ValueError, match="Current password is required"):
        update_profile(db, user_id, current_password="", new_password="newpass123")

    login("a@x.com", "secret123", db)


def test_update_profile_rejected_attempts_do_not_change_password(db):
    _, user_id, _ = register("a@x.com", "secret123", db)

    with pytest.raises(ValueError):
        update_profile(db, user_id, current_password="wrong-pass", new_password="newpass123")
    with pytest.raises(ValueError):
        update_profile(db, user_id, new_password="newpass123")

    login("a@x.com", "secret123", db)
    with pytest.raises(AuthError):
        login("a@x.com", "newpass123", db)


# --- Account deletion -------------------------------------------------------


def test_delete_account_wrong_password_is_401_and_keeps_user(db):
    register("a@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        delete_account(_user(db, "a@x.com"), "wrong-pass", db)

    assert exc.value.status_code == 401
    assert _user(db, "a@x.com") is not None


@pytest.mark.parametrize("password", [None, ""])
def test_delete_account_without_password_is_400_and_keeps_user(db, password):
    register("a@x.com", "secret123", db)

    with pytest.raises(AuthError) as exc:
        delete_account(_user(db, "a@x.com"), password, db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Password required for account deletion"
    assert _user(db, "a@x.com") is not None

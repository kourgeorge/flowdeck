"""bcrypt only uses 72 bytes of a password. bcrypt 5 raises ValueError past
that (a 500 for users); bcrypt 4 silently truncated. These tests pin the
behaviour: refuse long new passwords with a 400, keep old long-password
accounts able to log in, and never surface a 500."""

from __future__ import annotations

import bcrypt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import auth
from database import Base
from models.db_models import User
from services import auth_service, me_service
from services.auth_service import AuthError


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(auth_service, "send_welcome_email", lambda *_a, **_k: None)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _strict_bcrypt(monkeypatch):
    """Make bcrypt behave like bcrypt 5: refuse inputs over 72 bytes."""
    real_hashpw, real_checkpw = bcrypt.hashpw, bcrypt.checkpw

    def hashpw(password, salt):
        if len(password) > 72:
            raise ValueError("password cannot be longer than 72 bytes")
        return real_hashpw(password, salt)

    def checkpw(password, hashed):
        if len(password) > 72:
            raise ValueError("password cannot be longer than 72 bytes")
        return real_checkpw(password, hashed)

    monkeypatch.setattr(auth.bcrypt, "hashpw", hashpw)
    monkeypatch.setattr(auth.bcrypt, "checkpw", checkpw)


def _legacy_user(db, email: str, long_password: str) -> User:
    """An account made under bcrypt 4, which hashed only the first 72 bytes."""
    stored = bcrypt.hashpw(long_password.encode("utf-8")[:72], bcrypt.gensalt(4)).decode()
    user = User(email=email, hashed_password=stored, token_balance=0)
    db.add(user)
    db.commit()
    return user


def test_register_rejects_password_over_72_bytes(db):
    password = "é" * 37  # 37 characters, 74 UTF-8 bytes
    assert len(password) < 72 < len(password.encode("utf-8"))

    with pytest.raises(AuthError) as exc:
        auth_service.register("long@example.com", password, db)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Password must be at most 72 bytes"
    assert db.query(User).count() == 0


def test_register_accepts_exactly_72_bytes(db):
    _, user_id, _ = auth_service.register("edge@example.com", "a" * 72, db)
    assert db.query(User).filter(User.id == user_id).count() == 1


def test_hash_password_refuses_long_input_as_backstop():
    with pytest.raises(ValueError):
        auth.hash_password("a" * 73)


def test_update_profile_rejects_long_new_password_and_keeps_old(db):
    _, user_id, _ = auth_service.register("change@example.com", "oldpass1", db)

    with pytest.raises(ValueError, match="at most 72 bytes"):
        me_service.update_profile(
            db, user_id, current_password="oldpass1", new_password="b" * 73
        )

    db.expire_all()
    auth_service.login("change@example.com", "oldpass1", db)
    with pytest.raises(AuthError) as exc:
        auth_service.login("change@example.com", "b" * 73, db)
    assert exc.value.status_code == 401


def test_update_profile_long_password_maps_to_400(db, monkeypatch):
    from fastapi import HTTPException
    from routers import me as me_router

    _, user_id, _ = auth_service.register("route@example.com", "oldpass1", db)
    user = db.query(User).filter(User.id == user_id).one()
    body = me_router.UpdateProfileRequest(current_password="oldpass1", new_password="c" * 73)

    import asyncio

    with pytest.raises(HTTPException) as exc:
        asyncio.run(me_router.update_me(body=body, current_user=user, db=db))
    assert exc.value.status_code == 400
    assert exc.value.detail == "Password must be at most 72 bytes"


@pytest.mark.parametrize("strict", [False, True], ids=["bcrypt4", "bcrypt5-like"])
def test_login_long_password(db, monkeypatch, strict):
    long_password = "p" * 72 + "-tail"  # 77 bytes
    _legacy_user(db, "legacy@example.com", long_password)
    if strict:
        _strict_bcrypt(monkeypatch)

    _, _, email = auth_service.login("legacy@example.com", long_password, db)
    assert email == "legacy@example.com"

    with pytest.raises(AuthError) as exc:
        auth_service.login("legacy@example.com", "q" * 73, db)
    assert exc.value.status_code == 401


def test_login_wrong_long_password_on_normal_account_is_401(db, monkeypatch):
    auth_service.register("normal@example.com", "secret123", db)
    _strict_bcrypt(monkeypatch)
    with pytest.raises(AuthError) as exc:
        auth_service.login("normal@example.com", "z" * 73, db)
    assert exc.value.status_code == 401


def test_login_with_corrupt_stored_hash_is_401_not_500(db):
    db.add(User(email="bad@example.com", hashed_password="not-a-bcrypt-hash", token_balance=0))
    db.commit()
    with pytest.raises(AuthError) as exc:
        auth_service.login("bad@example.com", "whatever1", db)
    assert exc.value.status_code == 401


def test_delete_account_with_long_legacy_password_under_strict_bcrypt(db, monkeypatch):
    long_password = "d" * 80
    user = _legacy_user(db, "del@example.com", long_password)
    _strict_bcrypt(monkeypatch)

    with pytest.raises(AuthError) as exc:
        auth_service.delete_account(user, "e" * 80, db)
    assert exc.value.status_code == 401

    auth_service.delete_account(user, long_password, db)
    assert db.query(User).count() == 0

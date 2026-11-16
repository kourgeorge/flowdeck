"""API key endpoints: expires_at handling, and that deactivated, deleted, expired or legacy keys are refused."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
from database import Base, get_db
from models.db_models import ApiKey, User
from routers import api_keys


def _setup(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/keys.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        user = User(email="a@example.com", name="A")
        db.add(user)
        db.commit()
        subject = user.auth_subject

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(api_keys.router)
    app.dependency_overrides[get_db] = _get_db
    token = auth.create_access_token(subject)
    return TestClient(app), {"Authorization": f"Bearer {token}"}, Session


def _create(client, headers, expires_at):
    return client.post(
        "/api/api-keys", json={"name": "bot", "expires_at": expires_at}, headers=headers
    )


def test_naive_expires_at_is_rejected_with_400(tmp_path):
    client, headers, _ = _setup(tmp_path)
    resp = _create(client, headers, "2099-12-31T23:59:59")
    assert resp.status_code == 400
    assert "time zone" in resp.json()["detail"]


def test_offset_expiry_is_stored_as_utc_and_key_works(tmp_path):
    client, headers, Session = _setup(tmp_path)
    eastern = timezone(timedelta(hours=-5))
    target = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(microsecond=0)
    resp = _create(client, headers, target.astimezone(eastern).isoformat())
    assert resp.status_code == 201

    with Session() as db:
        stored = db.get(ApiKey, resp.json()["id"]).expires_at
    assert stored == target.replace(tzinfo=None)

    use = client.get(
        "/api/api-keys", headers={"Authorization": f"Bearer {resp.json()['key']}"}
    )
    assert use.status_code == 200


def test_past_expires_at_is_rejected(tmp_path):
    client, headers, _ = _setup(tmp_path)
    assert _create(client, headers, "2000-01-01T00:00:00Z").status_code == 400


def test_z_expires_at_is_accepted(tmp_path):
    client, headers, _ = _setup(tmp_path)
    assert _create(client, headers, "2099-12-31T23:59:59Z").status_code == 201


def _bearer(key):
    return {"Authorization": f"Bearer {key}"}


def _new_key(client, headers):
    resp = _create(client, headers, None)
    assert resp.status_code == 201
    return resp.json()["id"], resp.json()["key"]


def _other_users_key(Session):
    """A key owned by a second user, made directly so the caller never holds it."""
    from services import api_key_service

    with Session() as db:
        other = User(email="b@example.com", name="B")
        db.add(other)
        db.commit()
        api_key, full_key = api_key_service.create(db, other.id, "theirs")
        return api_key.id, full_key


def test_deactivated_key_is_refused(tmp_path):
    client, headers, _ = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    resp = client.patch(f"/api/api-keys/{key_id}/deactivate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 401


def test_reactivated_key_works_again(tmp_path):
    client, headers, _ = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    client.patch(f"/api/api-keys/{key_id}/deactivate", headers=headers)
    resp = client.patch(f"/api/api-keys/{key_id}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 200


def test_deleted_key_is_refused(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    assert client.delete(f"/api/api-keys/{key_id}", headers=headers).status_code == 204
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 401
    with Session() as db:
        assert db.get(ApiKey, key_id) is None


def test_delete_missing_key_is_404(tmp_path):
    client, headers, _ = _setup(tmp_path)
    assert client.delete("/api/api-keys/9999", headers=headers).status_code == 404


def test_deleting_twice_is_404_the_second_time(tmp_path):
    client, headers, _ = _setup(tmp_path)
    key_id, _ = _new_key(client, headers)
    assert client.delete(f"/api/api-keys/{key_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/api-keys/{key_id}", headers=headers).status_code == 404


def test_cannot_delete_another_users_key(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, their_key = _other_users_key(Session)
    resp = client.delete(f"/api/api-keys/{key_id}", headers=headers)
    assert resp.status_code == 404
    assert client.get("/api/api-keys", headers=_bearer(their_key)).status_code == 200


def test_cannot_deactivate_another_users_key(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, their_key = _other_users_key(Session)
    resp = client.patch(f"/api/api-keys/{key_id}/deactivate", headers=headers)
    assert resp.status_code == 404
    assert client.get("/api/api-keys", headers=_bearer(their_key)).status_code == 200


def test_cannot_activate_another_users_key(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, _ = _other_users_key(Session)
    with Session() as db:
        db.get(ApiKey, key_id).is_active = False
        db.commit()
    resp = client.patch(f"/api/api-keys/{key_id}/activate", headers=headers)
    assert resp.status_code == 404
    with Session() as db:
        assert db.get(ApiKey, key_id).is_active is False


def test_other_users_keys_are_not_listed(tmp_path):
    client, headers, Session = _setup(tmp_path)
    _other_users_key(Session)
    resp = client.get("/api/api-keys", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_expired_key_is_refused(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    with Session() as db:
        naive_utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.get(ApiKey, key_id).expires_at = naive_utc_now - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 401


def test_key_whose_owner_subject_changed_is_refused(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    with Session() as db:
        db.get(ApiKey, key_id).user_subject = "someone-else"
        db.commit()
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 401


def test_legacy_key_without_subject_is_refused(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, key = _new_key(client, headers)
    with Session() as db:
        db.get(ApiKey, key_id).user_subject = None
        db.commit()
    assert client.get("/api/api-keys", headers=_bearer(key)).status_code == 401


def test_legacy_key_cannot_be_reactivated(tmp_path):
    client, headers, Session = _setup(tmp_path)
    key_id, _ = _new_key(client, headers)
    with Session() as db:
        row = db.get(ApiKey, key_id)
        row.user_subject = None
        row.is_active = False
        db.commit()
    resp = client.patch(f"/api/api-keys/{key_id}/activate", headers=headers)
    assert resp.status_code == 404
    assert "Legacy key was revoked" in resp.json()["detail"]
    with Session() as db:
        assert db.get(ApiKey, key_id).is_active is False


def test_unknown_api_key_is_refused(tmp_path):
    client, _, _ = _setup(tmp_path)
    assert client.get("/api/api-keys", headers=_bearer("fd_live_nope")).status_code == 401

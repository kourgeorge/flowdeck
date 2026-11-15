"""POST /api/api-keys: expires_at must be time-zone aware and is stored as naive UTC."""
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

"""Subscriptions router: duplicate subscribes, ticker validation, and unknown-ticker PATCH/DELETE."""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth
from database import Base, get_db
from models.db_models import Subscription, User
from routers import subscriptions


def _setup(tmp_path, monkeypatch, wrap_session=None):
    engine = create_engine(
        f"sqlite:///{tmp_path}/subs.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        user = User(email="a@example.com", name="A")
        db.add(user)
        db.commit()
        subject, user_id = user.auth_subject, user.id

    def _get_db():
        db = Session()
        if wrap_session:
            wrap_session(db)
        try:
            yield db
        finally:
            db.close()

    sent = {"admin": [], "confirm": []}
    monkeypatch.setattr(
        subscriptions,
        "notify_admin_new_subscription",
        lambda user_email, ticker: sent["admin"].append(ticker),
    )
    monkeypatch.setattr(
        subscriptions,
        "send_subscription_confirmation",
        lambda user_email, ticker: sent["confirm"].append(ticker),
    )

    app = FastAPI()
    app.include_router(subscriptions.router)
    app.dependency_overrides[get_db] = _get_db
    token = auth.create_access_token(subject)
    return TestClient(app), {"Authorization": f"Bearer {token}"}, Session, user_id, sent


def test_double_subscribe_returns_201_once_row_and_emails_once(tmp_path, monkeypatch):
    client, headers, Session, _, sent = _setup(tmp_path, monkeypatch)
    first = client.post("/api/subscriptions", json={"ticker": " aapl "}, headers=headers)
    second = client.post("/api/subscriptions", json={"ticker": " aapl "}, headers=headers)

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["ticker"] == "AAPL" and second.json()["ticker"] == "AAPL"
    assert first.json()["id"] == second.json()["id"]
    with Session() as db:
        assert db.query(Subscription).count() == 1
    assert sent == {"admin": ["AAPL"], "confirm": ["AAPL"]}


def test_racing_insert_returns_existing_subscription(tmp_path, monkeypatch):
    # Simulate a second tab winning the race: right before this request's commit,
    # another session inserts the same (user, ticker), so the unique constraint
    # makes this commit raise IntegrityError.
    holder = {}

    def wrap(db):
        real_commit = db.commit
        state = {"done": False}

        def racing_commit():
            if not state["done"]:
                state["done"] = True
                with holder["Session"]() as other:
                    other.add(Subscription(user_id=holder["user_id"], ticker="MSFT"))
                    other.commit()
            return real_commit()

        db.commit = racing_commit

    client, headers, Session, user_id, sent = _setup(tmp_path, monkeypatch, wrap)
    holder.update(Session=Session, user_id=user_id)

    resp = client.post("/api/subscriptions", json={"ticker": "msft"}, headers=headers)

    assert resp.status_code == 201
    with Session() as db:
        rows = db.query(Subscription).all()
    assert len(rows) == 1
    assert resp.json()["id"] == rows[0].id
    assert resp.json()["ticker"] == "MSFT"
    assert sent == {"admin": [], "confirm": []}


def test_invalid_tickers_are_rejected_with_400(tmp_path, monkeypatch):
    client, headers, Session, _, sent = _setup(tmp_path, monkeypatch)
    for bad in ("A" * 200, "$$$; DROP"):
        resp = client.post("/api/subscriptions", json={"ticker": bad}, headers=headers)
        assert resp.status_code == 400, bad
    with Session() as db:
        assert db.query(Subscription).count() == 0
    assert sent == {"admin": [], "confirm": []}


def test_patch_unknown_is_404_and_delete_unknown_is_204(tmp_path, monkeypatch):
    client, headers, *_ = _setup(tmp_path, monkeypatch)
    patch = client.patch(
        "/api/subscriptions/NOPE", json={"email_updates": False}, headers=headers
    )
    assert patch.status_code == 404
    delete = client.delete("/api/subscriptions/NOPE", headers=headers)
    assert delete.status_code == 204

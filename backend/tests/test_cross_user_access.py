"""Another user's chats and briefs must look like they do not exist.

Each of these routes guards someone else's data with a single owner check
(get_session_for_user, get_turn_for_user, delete_session_for_user, the
session lookup in ChatTurnService.prepare_turn, digest_service.delete_brief
and the creator filter in send_brief_email). A 404, rather than 403, also
avoids telling user B that A's id exists.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from auth import get_current_user
from database import Base
from models.db_models import ChatMessage, ChatSession, ChatTurn, Execution, Usage, User
from routers import chat as chat_router
from routers import digest as digest_router

A, B = 1, 2


@pytest.fixture
def chat_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(User(id=A, email="a@example.com", hashed_password="x", token_balance=500))
    db.add(User(id=B, email="b@example.com", hashed_password="x", token_balance=500))
    db.commit()
    db.close()
    monkeypatch.setattr("services.chat_turn_service.SessionLocal", SessionLocal)
    yield SessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _client_as(SessionLocal, user_id: int) -> TestClient:
    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(digest_router.router)
    user = SimpleNamespace(id=user_id, email=f"{'a' if user_id == A else 'b'}@example.com")
    app.dependency_overrides[get_current_user] = lambda: user

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database.get_db] = _get_db
    return TestClient(app)


@pytest.fixture
def a_chat(chat_db):
    """A's session with one question, one answer and a finished turn."""
    db = chat_db()
    session = ChatSession(user_id=A, title="A's question")
    db.add(session)
    db.flush()
    question = ChatMessage(session_id=session.id, role="user", content="What about AAPL?", sort_order=0)
    answer = ChatMessage(session_id=session.id, role="assistant", content="It's fine.", sort_order=1)
    db.add_all([question, answer])
    db.flush()
    turn = ChatTurn(session_id=session.id, user_id=A, status="completed",
                    user_message_id=question.id, assistant_message_id=answer.id)
    db.add(turn)
    db.commit()
    ids = SimpleNamespace(session_id=session.id, turn_id=turn.id)
    db.close()
    return ids


@pytest.fixture
def a_brief(chat_db):
    db = chat_db()
    ex = Execution(execution_type="daily_digest", subject_type="user_date",
                   subject_id=f"{A}:2026-11-16", creator_id=A, status="completed")
    db.add(ex)
    db.commit()
    ex_id = ex.id
    db.close()
    return ex_id


def _message_contents(SessionLocal, session_id: int) -> list[str]:
    db = SessionLocal()
    try:
        rows = db.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.sort_order).all()
        return [m.content for m in rows]
    finally:
        db.close()


def _exists(SessionLocal, model, row_id: int) -> bool:
    db = SessionLocal()
    try:
        return db.get(model, row_id) is not None
    finally:
        db.close()


def test_owner_can_read_own_session_so_404s_below_are_about_ownership(chat_db, a_chat):
    r = _client_as(chat_db, A).get(f"/api/chat/sessions/{a_chat.session_id}")
    assert r.status_code == 200, r.text
    assert [m["content"] for m in r.json()["messages"]] == ["What about AAPL?", "It's fine."]


def test_other_user_cannot_read_session(chat_db, a_chat):
    r = _client_as(chat_db, B).get(f"/api/chat/sessions/{a_chat.session_id}")
    assert r.status_code == 404, r.text


def test_other_user_cannot_read_turn(chat_db, a_chat):
    r = _client_as(chat_db, B).get(f"/api/chat/turns/{a_chat.turn_id}")
    assert r.status_code == 404, r.text


def test_other_user_cannot_delete_session_and_it_survives(chat_db, a_chat):
    r = _client_as(chat_db, B).delete(f"/api/chat/sessions/{a_chat.session_id}")
    assert r.status_code == 404, r.text
    assert _exists(chat_db, ChatSession, a_chat.session_id)
    assert _exists(chat_db, ChatTurn, a_chat.turn_id)
    assert _message_contents(chat_db, a_chat.session_id) == ["What about AAPL?", "It's fine."]


def test_other_user_cannot_post_into_session_and_is_not_charged(chat_db, a_chat, monkeypatch):
    # If the owner check ever slips, fail loudly here instead of reaching a real LLM.
    def _no_llm():
        raise AssertionError("chat agent must not run for another user's session")
    monkeypatch.setattr("services.chat_turn_service.get_chat_service", _no_llm)

    r = _client_as(chat_db, B).post("/api/chat", json={
        "session_id": a_chat.session_id,
        "messages": [{"role": "user", "content": "Injected by B"}],
    })
    assert r.status_code == 404, r.text
    assert _message_contents(chat_db, a_chat.session_id) == ["What about AAPL?", "It's fine."]
    db = chat_db()
    try:
        assert db.query(Usage).filter(Usage.transaction_type == "chat_reserve").count() == 0
        assert db.query(ChatTurn).count() == 1
        assert db.query(ChatSession).count() == 1
    finally:
        db.close()


def test_other_user_cannot_delete_brief_and_it_survives(chat_db, a_brief):
    r = _client_as(chat_db, B).delete(f"/api/digest/briefs/{a_brief}")
    assert r.status_code == 404, r.text
    assert _exists(chat_db, Execution, a_brief)


def test_other_user_cannot_email_brief(chat_db, a_brief, monkeypatch):
    sent = []
    monkeypatch.setattr(digest_router, "send_daily_digest_email_to_user",
                        lambda execution_id, email: sent.append((execution_id, email)) or True)
    r = _client_as(chat_db, B).post(f"/api/digest/briefs/{a_brief}/send-email")
    assert r.status_code == 404, r.text
    assert sent == []
    assert _exists(chat_db, Execution, a_brief)

"""Tests for the public contact form route: field caps, error handling, rate limit."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import contact

VALID = {"name": "Ada", "email": "ada@example.com", "message": "Hello"}


@pytest.fixture(autouse=True)
def _reset_limiter():
    contact.reset_rate_limit()
    yield
    contact.reset_rate_limit()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(contact.router)
    # raise_server_exceptions=False so a 500 comes back as a response we can inspect.
    return TestClient(app, raise_server_exceptions=False)


def _fake_sender(calls, result=True):
    def fake(name, email, message):
        calls.append((name, email, message))
        return result

    return fake


def test_valid_submission_sends(monkeypatch):
    calls = []
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender(calls))
    resp = _client().post("/api/contact", json=VALID)
    assert resp.status_code == 200
    assert calls == [("Ada", "ada@example.com", "Hello")]


@pytest.mark.parametrize(
    "override",
    [
        {"message": "x" * 10001},
        {"message": "x" * 5001},
        {"name": "n" * 201},
        {"email": "a" * 250 + "@example.com"},
        {"email": "not-an-email"},
    ],
)
def test_oversized_or_invalid_fields_give_422_and_never_send(monkeypatch, override):
    calls = []
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender(calls))
    resp = _client().post("/api/contact", json={**VALID, **override})
    assert resp.status_code == 422
    assert calls == []


def test_fields_at_the_limit_are_accepted(monkeypatch):
    calls = []
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender(calls))
    body = {**VALID, "name": "n" * 200, "message": "x" * 5000}
    resp = _client().post("/api/contact", json=body)
    assert resp.status_code == 200
    assert len(calls) == 1


def test_sender_returning_false_gives_503(monkeypatch):
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender([], result=False))
    resp = _client().post("/api/contact", json=VALID)
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"]


def test_sender_exception_gives_500_without_leaking(monkeypatch):
    def boom(name, email, message):
        raise RuntimeError("secret")

    monkeypatch.setattr(contact, "send_contact_form_email", boom)
    resp = _client().post("/api/contact", json=VALID)
    assert resp.status_code == 500
    assert "secret" not in resp.text


def test_sixth_submission_in_window_gives_429(monkeypatch):
    calls = []
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender(calls))
    client = _client()
    for _ in range(5):
        assert client.post("/api/contact", json=VALID).status_code == 200
    resp = client.post("/api/contact", json=VALID)
    assert resp.status_code == 429
    assert "Too many" in resp.json()["detail"]
    assert len(calls) == 5


def test_spoofed_forwarded_for_does_not_bypass_limit(monkeypatch):
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender([]))
    client = _client()
    for i in range(5):
        r = client.post("/api/contact", json=VALID, headers={"X-Forwarded-For": f"10.0.0.{i}"})
        assert r.status_code == 200
    r = client.post("/api/contact", json=VALID, headers={"X-Forwarded-For": "10.0.0.99"})
    assert r.status_code == 429


def test_window_expiry_allows_again(monkeypatch):
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender([]))
    now = [1000.0]
    # Swap only the router's view of `time` so the test client's own clock is untouched.
    monkeypatch.setattr(contact, "time", SimpleNamespace(monotonic=lambda: now[0]))
    client = _client()
    for _ in range(5):
        assert client.post("/api/contact", json=VALID).status_code == 200
    assert client.post("/api/contact", json=VALID).status_code == 429
    now[0] += contact.RATE_LIMIT_WINDOW_SECONDS + 1
    assert client.post("/api/contact", json=VALID).status_code == 200


def _proxied_client(peer_ip: str) -> TestClient:
    """App wrapped the way uvicorn runs it in production: ProxyHeadersMiddleware
    trusting only 127.0.0.1 (uvicorn's default --forwarded-allow-ips).

    TestClient always reports the peer as "testclient", so a small shim sets the
    socket peer to `peer_ip` first, standing in for Caddy (or an attacker)
    connecting to port 8002.
    """
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app = FastAPI()
    app.include_router(contact.router)
    proxied = ProxyHeadersMiddleware(app, trusted_hosts=["127.0.0.1"])

    async def set_peer(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = {**scope, "client": (peer_ip, 50000)}
        await proxied(scope, receive, send)

    return TestClient(set_peer, raise_server_exceptions=False)


def test_trusted_proxy_gives_each_forwarded_ip_its_own_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender(calls))
    client = _proxied_client("127.0.0.1")
    for visitor in ("203.0.113.7", "198.51.100.23"):
        headers = {"X-Forwarded-For": visitor}
        for _ in range(5):
            assert client.post("/api/contact", json=VALID, headers=headers).status_code == 200
        assert client.post("/api/contact", json=VALID, headers=headers).status_code == 429
    assert len(calls) == 10


def test_untrusted_peer_cannot_fake_forwarded_for(monkeypatch):
    # A caller reaching port 8002 directly (not via the trusted proxy) must not
    # get a fresh limit by rotating X-Forwarded-For.
    monkeypatch.setattr(contact, "send_contact_form_email", _fake_sender([]))
    client = _proxied_client("192.0.2.50")
    for i in range(5):
        r = client.post("/api/contact", json=VALID, headers={"X-Forwarded-For": f"10.0.0.{i}"})
        assert r.status_code == 200
    r = client.post("/api/contact", json=VALID, headers={"X-Forwarded-For": "10.0.0.99"})
    assert r.status_code == 429

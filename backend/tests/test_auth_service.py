from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import Subscription, User, UserProfile
from services.auth_service import DEFAULT_SIGNUP_TICKERS, google_callback, register


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class TestAuthService(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_register_adds_default_signup_subscriptions_without_email_updates(self) -> None:
        with patch("services.auth_service.send_welcome_email") as mock_welcome:
            _, user_id, email = register("newuser@example.com", "secret123", self.db)

        self.assertEqual(email, "newuser@example.com")
        user = self.db.query(User).filter(User.id == user_id).first()
        self.assertIsNotNone(user)
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        self.assertIsNotNone(profile)

        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.ticker.asc())
            .all()
        )
        self.assertEqual([sub.ticker for sub in subscriptions], sorted(DEFAULT_SIGNUP_TICKERS))
        self.assertTrue(all(sub.email_updates is False for sub in subscriptions))
        mock_welcome.assert_called_once_with("newuser@example.com")

    def test_google_callback_adds_default_signup_subscriptions_without_email_updates(self) -> None:
        fake_requests = types.ModuleType("requests")
        fake_requests.post = lambda *args, **kwargs: _FakeResponse({"id_token": "fake-jwt"})

        fake_google_requests = types.ModuleType("google.auth.transport.requests")

        class _Request:
            pass

        fake_google_requests.Request = _Request

        fake_id_token = types.ModuleType("google.oauth2.id_token")
        fake_id_token.verify_oauth2_token = lambda *args, **kwargs: {
            "sub": "google-user-123",
            "email": "googleuser@example.com",
            "name": "Google User",
        }

        fake_google = types.ModuleType("google")
        fake_google_auth = types.ModuleType("google.auth")
        fake_google_auth_transport = types.ModuleType("google.auth.transport")
        fake_google_oauth2 = types.ModuleType("google.oauth2")

        patched_modules = {
            "requests": fake_requests,
            "google": fake_google,
            "google.auth": fake_google_auth,
            "google.auth.transport": fake_google_auth_transport,
            "google.auth.transport.requests": fake_google_requests,
            "google.oauth2": fake_google_oauth2,
            "google.oauth2.id_token": fake_id_token,
        }

        with patch.dict(sys.modules, patched_modules), patch(
            "services.auth_service.send_welcome_email"
        ) as mock_welcome:
            user, _, is_new_user = google_callback(
                "oauth-code",
                self.db,
                client_id="client-id",
                client_secret="client-secret",
                redirect_uri="https://example.com/callback",
            )

        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .order_by(Subscription.ticker.asc())
            .all()
        )
        profile = self.db.query(UserProfile).filter(UserProfile.user_id == user.id).first()

        self.assertIsNotNone(profile)
        self.assertTrue(is_new_user)
        self.assertEqual([sub.ticker for sub in subscriptions], sorted(DEFAULT_SIGNUP_TICKERS))
        self.assertTrue(all(sub.email_updates is False for sub in subscriptions))
        mock_welcome.assert_called_once_with("googleuser@example.com")


if __name__ == "__main__":
    unittest.main()

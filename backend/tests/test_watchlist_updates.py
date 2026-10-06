"""Isolated morning notification checks; no real mail, market data, or model calls."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
from models.db_models import Subscription, User, UserSchedule, WatchlistUpdate
from services import watchlist_update_service as service


def history(change=7, session_day="2026-10-05"):
    previous_day = (date.fromisoformat(session_day) - timedelta(days=1)).isoformat()
    return {"data": [{"date": previous_day, "close": 100},
                     {"date": session_day, "close": 100 + change}]}


ARTICLE = {"headline": "What changed", "introduction": "A sourced introduction.",
           "sections": [{"heading": "The evidence", "body": "The cause remains uncertain."}],
           "watch_next": "Watch the next filing.",
           "sources": [{"title": "Company filing", "url": "https://example.com/filing",
                        "publisher": "Example", "published_time": "2026-10-05"}]}


class TestMovementThreshold(unittest.TestCase):
    def test_strict_six_percent_boundary_in_both_directions(self):
        for change, eligible in [(6, False), (-6, False), (6.001, True), (-6.001, True), (0, False)]:
            with self.subTest(change=change):
                self.assertEqual(service.latest_move("TEST", history(change), date(2026, 10, 6)) is not None, eligible)

    def test_forming_candle_is_not_a_completed_move(self):
        data = history(1)
        data["data"].append({"date": "2026-10-06", "close": 130})
        self.assertIsNone(service.latest_move("TEST", data, date(2026, 10, 6)))

    def test_stale_or_invalid_data_does_not_trigger(self):
        for payload in ({"data": []}, history(10, "2026-09-25"), history(float("nan")), history(float("inf"))):
            self.assertIsNone(service.latest_move("TEST", payload, date(2026, 10, 6)))

    def test_adjusted_closes_avoid_a_split_alert(self):
        data = {"data": [{"date": "2026-10-04", "close": 100, "adj_close": 50},
                         {"date": "2026-10-05", "close": 51, "adj_close": 51}]}
        self.assertIsNone(service.latest_move("TEST", data, date(2026, 10, 6)))


class TestWatchlistUpdates(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([User(id=1, email="one@example.invalid"), User(id=2, email="two@example.invalid")])
        self.db.add(Subscription(user_id=1, ticker="TEST", email_updates=True))
        self.db.commit()
        self.now = datetime(2026, 10, 6, 8, 5, tzinfo=timezone.utc)
        self.gateway = Mock()
        self.gateway.get_historical.return_value = history()
        self.researcher = Mock(return_value=ARTICLE)
        self.sender = Mock(return_value=True)
        self.score = patch("processing.get_ticker_event_summary", return_value=SimpleNamespace(event_score=12, events=[]))
        self.score_mock = self.score.start()
        self.environment = patch.dict("os.environ", {"DIGEST_DEFAULT_TIMEZONE": "UTC"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.score.stop()
        self.db.close()
        self.engine.dispose()

    def run_updates(self, now=None):
        return service.run_watchlist_updates(self.db, now=now or self.now, gateway=self.gateway,
                                            researcher=self.researcher, sender=self.sender)

    def test_default_enabled_and_combined_article(self):
        self.db.add(Subscription(user_id=1, ticker="SECOND", email_updates=True))
        self.db.commit()
        self.assertTrue(service.get_preferences(self.db, 1)["enabled"])
        result = self.run_updates()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(self.researcher.call_count, 1)
        self.assertEqual({m["ticker"] for m in self.sender.call_args.args[2]}, {"TEST", "SECOND"})
        self.assertEqual(self.db.query(WatchlistUpdate).one().status, "sent")

    def test_small_move_never_calls_event_engine_llm_or_mail(self):
        self.gateway.get_historical.return_value = history(6)
        self.run_updates()
        self.score_mock.assert_not_called()
        self.researcher.assert_not_called()
        self.sender.assert_not_called()

    def test_large_move_with_low_event_score_never_calls_llm_or_mail(self):
        self.score_mock.return_value.event_score = service.MIN_EVENT_SCORE - .01
        self.run_updates()
        self.researcher.assert_not_called()
        self.sender.assert_not_called()

    def test_event_score_boundary_is_inclusive(self):
        self.score_mock.return_value.event_score = service.MIN_EVENT_SCORE
        self.assertEqual(self.run_updates()["sent"], 1)

    def test_user_opt_out_and_per_ticker_opt_out(self):
        service.set_preferences(self.db, 1, enabled=False, timezone_name="UTC")
        self.run_updates()
        self.gateway.get_historical.assert_not_called()
        service.set_preferences(self.db, 1, enabled=True, timezone_name="UTC")
        self.db.query(Subscription).update({"email_updates": False})
        self.db.commit()
        self.run_updates()
        self.sender.assert_not_called()

    def test_users_are_isolated_and_opt_out_is_persistent(self):
        self.db.add(Subscription(user_id=2, ticker="TEST", email_updates=True))
        self.db.commit()
        service.set_preferences(self.db, 1, enabled=False, timezone_name="UTC")
        self.run_updates()
        self.assertEqual(self.sender.call_args.args[0], "two@example.invalid")
        self.assertEqual(self.sender.call_count, 1)
        self.assertFalse(service.get_preferences(self.db, 1)["enabled"])

    def test_repeated_ticks_and_next_morning_do_not_repeat_same_session(self):
        self.run_updates()
        self.run_updates(self.now + timedelta(minutes=15))
        self.run_updates(self.now + timedelta(days=1))
        self.assertEqual(self.sender.call_count, 1)
        self.assertEqual(self.researcher.call_count, 1)

    def test_new_session_can_send_next_day(self):
        self.run_updates()
        self.gateway.get_historical.return_value = history(-8, "2026-10-06")
        self.run_updates(self.now + timedelta(days=1))
        self.assertEqual(self.sender.call_count, 2)

    def test_saved_timezone_and_morning_window(self):
        service.set_preferences(self.db, 1, enabled=True, timezone_name="America/New_York")
        self.run_updates()  # 04:05 local
        self.sender.assert_not_called()
        self.run_updates(datetime(2026, 10, 6, 12, 5, tzinfo=timezone.utc))
        self.assertEqual(self.sender.call_count, 1)

    def test_inherits_saved_digest_timezone_and_rejects_invalid_zone(self):
        self.db.add(UserSchedule(user_id=1, schedule_type="daily_digest", cron_expression="0 8 * * *",
                                 timezone="Asia/Jerusalem"))
        self.db.commit()
        self.assertEqual(service.get_preferences(self.db, 1)["timezone"], "Asia/Jerusalem")
        with self.assertRaises(ValueError):
            service.set_preferences(self.db, 1, enabled=False, timezone_name="Not/AZone")

    def test_research_failure_retries_with_limit_and_no_mail(self):
        self.researcher.side_effect = RuntimeError("model unavailable")
        for minutes in (0, 1, 15, 30, 45):
            self.run_updates(self.now + timedelta(minutes=minutes))
        self.assertEqual(self.researcher.call_count, 3)
        self.sender.assert_not_called()

    def test_opt_out_during_research_prevents_send(self):
        def opt_out(*args):
            service.set_preferences(self.db, 1, enabled=False, timezone_name="UTC")
            return ARTICLE
        self.researcher.side_effect = opt_out
        self.run_updates()
        self.sender.assert_not_called()

    def test_unfollow_during_research_prevents_send(self):
        def unfollow(*args):
            self.db.query(Subscription).delete()
            self.db.commit()
            return ARTICLE
        self.researcher.side_effect = unfollow
        self.run_updates()
        self.sender.assert_not_called()

    def test_unknown_delivery_is_not_retried_automatically(self):
        self.sender.return_value = False
        self.run_updates()
        self.run_updates(self.now + timedelta(minutes=15))
        self.run_updates(self.now + timedelta(days=1))
        self.assertEqual(self.sender.call_count, 1)
        self.assertEqual(self.db.query(WatchlistUpdate).order_by(WatchlistUpdate.id).first().status, "delivery_unknown")

    def test_active_claim_is_not_claimed_twice(self):
        now = self.now.replace(tzinfo=None)
        self.assertIsNotNone(service._claim(self.db, 1, self.now.date(), now))
        self.assertIsNone(service._claim(self.db, 1, self.now.date(), now))

    def test_expired_worker_cannot_send_after_lease_is_reclaimed(self):
        now = self.now.replace(tzinfo=None)
        first = service._claim(self.db, 1, self.now.date(), now)
        row_id, first_attempt = first.id, first.attempts
        second = service._claim(self.db, 1, self.now.date(), now + timedelta(hours=2, minutes=1))
        self.assertEqual(second.attempts, 2)
        self.assertFalse(service._finish_phase(self.db, row_id, first_attempt, {"status": "sending"}))
        self.db.refresh(second)
        self.assertEqual(second.status, "researching")

    def test_api_only_changes_current_user_and_validates_timezone(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from auth import get_current_user
        from database import get_db
        from routers.schedule import router
        # Use route functions directly so the in-memory SQLite session stays in its owning thread.
        from routers.schedule import get_watchlist_notifications, update_watchlist_notifications, WatchlistUpdatePreference
        user = self.db.query(User).filter_by(id=1).one()
        self.assertTrue(get_watchlist_notifications(current_user=user, db=self.db)["enabled"])
        result = update_watchlist_notifications(WatchlistUpdatePreference(enabled=False, timezone="UTC"),
                                               current_user=user, db=self.db)
        self.assertFalse(result["enabled"])
        self.assertTrue(service.get_preferences(self.db, 2)["enabled"])
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: None
        # No auth override: the actual dependency must reject unauthenticated requests.
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/watchlist/notifications").status_code, 401)
            self.assertEqual(client.put("/api/watchlist/notifications", json={"enabled": False}).status_code, 401)

    def test_no_silent_twenty_five_ticker_limit(self):
        self.db.add_all([Subscription(user_id=1, ticker=f"T{i:02}", email_updates=True) for i in range(26)])
        self.db.commit()
        self.gateway.get_historical.side_effect = lambda ticker, **_: history(7 if ticker == "T25" else 0)
        self.run_updates()
        self.assertEqual(self.gateway.get_historical.call_count, 27)
        self.assertEqual(self.sender.call_args.args[2][0]["ticker"], "T25")


class TestResearchAndEmail(unittest.TestCase):
    def test_two_pass_analysis_reads_articles_and_keeps_verified_sources(self):
        gateway = Mock()
        gateway.get_news.return_value = {"articles": [
            {"title": "A filing", "summary": "A company update.", "link": "https://example.com/filing"}]}
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="Evidence and alternative explanations.")
        model.with_structured_output.return_value.invoke.return_value = service.WatchlistArticle.model_validate(ARTICLE)
        with patch("ai_engine.llm_provider.get_llm", return_value=model), \
             patch("ai_engine.tradingagents.agents.utils.article_fetcher.enrich_articles_with_content") as enrich:
            result = service.research_article(gateway, [{"ticker": "TEST"}], ["TEST"])
        enrich.assert_called_once()
        model.invoke.assert_called_once()
        model.with_structured_output.return_value.invoke.assert_called_once()
        self.assertEqual(result["sources"][0]["url"], "https://example.com/filing")

    def test_empty_news_does_not_produce_an_article(self):
        gateway = Mock()
        gateway.get_news.return_value = {"articles": []}
        with patch("ai_engine.llm_provider.get_llm") as model:
            with self.assertRaises(RuntimeError):
                service.research_article(gateway, [{"ticker": "TEST"}], ["TEST"])
            model.assert_not_called()

    def test_email_escapes_model_html_and_has_opt_out_link(self):
        from services import email_service
        article = {**ARTICLE, "headline": "<script>bad()</script>"}
        moves = [{"ticker": "TEST", "change_percent": -7, "session_date": "2026-10-05", "price_basis": "close"}]
        with patch.object(email_service, "_get_smtp_password", return_value="dummy"), \
             patch.object(email_service, "_send_via_smtp", return_value=True) as send:
            self.assertTrue(email_service.send_watchlist_update_email("test@example.invalid", article, moves, "2026-10-06"))
        html = send.call_args.args[3]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Turn off morning watchlist updates", html)
        self.assertIn("-7.00%", html)


if __name__ == "__main__":
    unittest.main()

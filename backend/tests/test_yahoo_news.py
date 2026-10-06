"""Regression checks for Yahoo search, shared caching, and progressive news feeds."""
from __future__ import annotations

import asyncio
import json
import threading
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_layer.market import MarketDataLayer
from data_layer.vendors import yahoo_news as yahoo
from data_layer.vendors.y_finance import get_news_app_format, get_yfinance_news
from routers.data_api import data_news_batch_stream, news_router
from services import data_cache
from services.news_fetcher import get_news_yahoo


def article(uuid="one", timestamp=None):
    return {"uuid": uuid, "title": "Company announces results", "publisher": "Reuters",
            "link": f"https://example.com/{uuid}", "type": "STORY",
            "providerPublishTime": timestamp or int(datetime.now(timezone.utc).timestamp()) - 60}


class TestYahooSearch(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.patch = patch.object(yahoo, "get_yf_session", return_value=self.session)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def respond(self, data):
        self.session.get.return_value.json.return_value = data

    def test_working_endpoint_and_normalization(self):
        raw = article()
        raw["thumbnail"] = {"resolutions": [{"url": "https://example.com/image.jpg"}]}
        self.respond({"news": [raw, raw]})
        result = yahoo.get_ticker_news(" aapl ")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["articles"][0]["thumbnail"], "https://example.com/image.jpg")
        self.assertTrue(result["articles"][0]["published_time"].endswith("+00:00"))
        self.session.get.assert_called_once_with(
            yahoo.SEARCH_URL, params={"q": "AAPL", "newsCount": 20, "quotesCount": 0}, timeout=15)

    def test_nested_article_timezone_and_stable_missing_id(self):
        raw = {"content": {"title": "Results", "provider": {"displayName": "Reuters"},
                           "canonicalUrl": {"url": "https://example.com/story"},
                           "pubDate": "2026-10-06T10:30:00.123+03:00", "summary": "Details"}}
        result = yahoo.parse_article(raw)
        self.assertEqual(result["published_time"], "2026-10-06T07:30:00+00:00")
        self.assertEqual(result["summary"], "Details")
        self.assertEqual(result["uuid"], yahoo.parse_article(raw)["uuid"])

    def test_legitimate_empty_result(self):
        self.respond({"news": []})
        self.assertEqual(yahoo.get_ticker_news("AAPL")["count"], 0)

    def test_provider_schema_failures_are_not_empty_successes(self):
        for payload in ({}, {"news": None}, [], {"news": [{}]}):
            with self.subTest(payload=payload):
                self.respond(payload)
                with self.assertRaises(yahoo.YahooNewsError):
                    yahoo.search_news("AAPL")

    def test_http_and_json_failures_propagate(self):
        for failure in ("404", "429", "timeout"):
            with self.subTest(failure=failure):
                self.session.get.side_effect = RuntimeError(failure)
                with self.assertRaises(yahoo.YahooNewsError):
                    yahoo.search_news("AAPL")
        self.session.get.side_effect = None
        self.session.get.return_value.json.side_effect = ValueError("invalid JSON")
        with self.assertRaises(yahoo.YahooNewsError):
            yahoo.search_news("AAPL")

    def test_response_http_status_is_checked(self):
        self.respond({"news": []})
        self.session.get.return_value.raise_for_status.side_effect = RuntimeError("HTTP 404")
        with self.assertRaises(yahoo.YahooNewsError):
            yahoo.search_news("AAPL")

    def test_legacy_and_app_entry_points_use_search_and_filter_dates(self):
        def ts(day):
            return int(datetime(2026, 10, day, 12, tzinfo=timezone.utc).timestamp())
        self.respond({"news": [article("before", ts(3)), article("inside", ts(5)), article("after", ts(7))]})
        legacy = json.loads(get_yfinance_news("aapl", "2026-10-04", "2026-10-06"))
        self.assertEqual([a["uuid"] for a in legacy["articles"]], ["inside"])
        self.respond({"news": [article()]})
        self.assertEqual(get_news_app_format("AAPL")["count"], 1)

    def test_macro_news_query_uses_search_with_sources(self):
        self.respond({"news": [article(timestamp=int(datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()))]})
        text = yahoo.get_global_news_yahoo("2026-10-06", query="inflation")
        self.assertIn("Source: https://example.com/one", text)
        self.assertEqual(self.session.get.call_args.kwargs["params"]["q"], "inflation")

    def test_default_global_vendor_is_yahoo(self):
        from data_layer.vendors import interface
        self.respond({"news": []})
        with patch.object(interface, "get_config", return_value={"data_vendors": {"news_data": "yfinance"}}):
            result = interface.get_global_news("2026-10-06")
        self.assertIn("Yahoo Finance Search", result)
        self.session.get.assert_called_once()


class TestNewsCache(unittest.TestCase):
    def setUp(self):
        self.store = data_cache._TTLStore(maxsize=128)
        self.patch = patch.object(data_cache, "_store", self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.layer = MarketDataLayer()

    @patch("data_layer.market.yf_get_news")
    def test_failed_fetch_retries_and_success_is_shared_with_legacy(self, fetch):
        good = {"ticker": "AAPL", "articles": [yahoo.parse_article(article())], "count": 1}
        fetch.side_effect = [yahoo.YahooNewsError("unavailable"), good]
        self.assertIn("error", self.layer.get_news("AAPL"))
        self.assertEqual(get_news_yahoo("AAPL"), good)
        self.assertEqual(self.layer.get_news("AAPL"), good)
        self.assertEqual(fetch.call_count, 2)

    @patch("data_layer.market.yf_get_news")
    def test_error_envelopes_are_never_cached(self, fetch):
        fetch.return_value = {"error": "unavailable", "articles": [], "count": 0}
        self.layer.get_news("AAPL")
        self.layer.get_news("AAPL")
        self.assertEqual(fetch.call_count, 2)

    @patch("data_layer.market.yf_get_news")
    def test_old_empty_cache_is_bypassed_and_partial_failures_survive_batch(self, fetch):
        self.store.set("news:AAPL:yfinance:7", {"articles": [], "count": 0}, 3600)
        def response(ticker, lookback_days=7):
            if ticker == "MSFT":
                raise yahoo.YahooNewsError("unavailable")
            return {"articles": [yahoo.parse_article(article())], "count": 1}
        fetch.side_effect = response
        result = self.layer.get_news_batch([" aapl ", "MSFT", "AAPL"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["articles"][0]["tickers"], ["AAPL"])
        self.assertEqual(result["errors"], {"MSFT": "unavailable"})
        self.assertEqual(fetch.call_count, 2)


class TestNewsStreaming(unittest.IsolatedAsyncioTestCase):
    async def stream(self, tickers, fetch):
        with patch("routers.data_api._gateway", return_value=Mock(get_news=fetch)):
            response = await data_news_batch_stream(tickers=tickers, lookback_days=7)
            return [json.loads(line) async for line in response.body_iterator]

    async def test_empty_input_still_completes(self):
        chunks = await self.stream("", Mock())
        self.assertTrue(chunks[-1]["completed"])
        self.assertEqual(chunks[-1]["total_tickers"], 0)

    async def test_shared_articles_keep_all_tickers_and_finish(self):
        chunks = await self.stream("AAPL,MSFT,AAPL", Mock(return_value={"articles": [yahoo.parse_article(article())]}))
        self.assertTrue(chunks[-1]["completed"])
        self.assertEqual(chunks[-1]["total_articles"], 1)
        self.assertEqual(chunks[-1]["total_tickers"], 2)
        self.assertEqual(set(chunks[-2]["articles"][0]["tickers"]), {"AAPL", "MSFT"})

    async def test_partial_and_total_failures_are_explicit(self):
        def fetch(ticker, lookback_days=7):
            if ticker == "MSFT":
                raise yahoo.YahooNewsError("unavailable")
            return {"articles": [yahoo.parse_article(article())]}
        chunks = await self.stream("AAPL,MSFT", fetch)
        self.assertTrue(chunks[-1]["completed"])
        self.assertEqual(chunks[-1]["total_articles"], 1)
        self.assertEqual(chunks[-1]["errors"], {"MSFT": "unavailable"})
        chunks = await self.stream("MSFT", Mock(return_value={"articles": [], "error": "unavailable"}))
        self.assertTrue(chunks[-1]["completed"])
        self.assertEqual(chunks[-1]["errors"], {"MSFT": "unavailable"})

    async def test_empty_last_ticker_does_not_leave_stream_open(self):
        def fetch(ticker, lookback_days=7):
            return {"articles": [yahoo.parse_article(article())] if ticker == "AAPL" else []}
        chunks = await self.stream("AAPL,MSFT", fetch)
        self.assertTrue(chunks[-1]["completed"])
        self.assertEqual(chunks[-1]["completed_tickers"], 2)

    async def test_vendor_wait_does_not_block_event_loop(self):
        release = threading.Event()
        def fetch(*args, **kwargs):
            if not release.wait(1):
                raise RuntimeError("event loop blocked")
            return {"articles": []}
        async def heartbeat():
            await asyncio.sleep(0.02)
            release.set()
        beat = asyncio.create_task(heartbeat())
        chunks = await self.stream("AAPL", fetch)
        await beat
        self.assertEqual(chunks[-1]["errors"], {})


class TestNewsConsumers(unittest.TestCase):
    def test_http_stream_contract(self):
        app = FastAPI()
        app.include_router(news_router)
        gw = Mock()
        gw.get_news.return_value = {"articles": [], "error": "unavailable"}
        with patch("routers.data_api._gateway", return_value=gw):
            response = TestClient(app).get("/api/data/news/batch/stream?tickers=AAPL")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.headers["content-type"])
        self.assertTrue(json.loads(response.text.splitlines()[-1])["completed"])

    def test_agent_client_propagates_errors_and_filters_requested_dates(self):
        from ai_engine.tradingagents.datasources.info_service_client import get_news
        with patch("ai_engine.tradingagents.datasources.info_service_client._get", return_value={"error": "unavailable"}):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                get_news("AAPL", "2026-10-01", "2026-10-05", base_url="http://backend")
        raw = [article("inside", 1791158400), article("outside", 1791504000)]
        with patch("ai_engine.tradingagents.datasources.info_service_client._get",
                   return_value={"articles": [yahoo.parse_article(a) for a in raw]}) as request:
            result = json.loads(get_news("AAPL", "2026-10-01", "2026-10-05", base_url="http://backend"))
        self.assertEqual([a["uuid"] for a in result["articles"]], ["inside"])
        self.assertLessEqual(request.call_args.kwargs["params"]["lookback_days"], 90)

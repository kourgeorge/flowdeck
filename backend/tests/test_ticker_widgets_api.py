from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.tickers import router as tickers_router


app = FastAPI()
app.include_router(tickers_router)


class TestTickerWidgetsAPI(unittest.TestCase):
    def test_widgets_endpoint_can_return_latest_analyzed_tickers_overall(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_latest_analyzed_tickers_paginated.return_value = (["MSFT", "AAPL"], 2)
        mock_gateway.get_quotes_batch.return_value = {
            "AAPL": {
                "ticker": "AAPL",
                "current_price": 100.0,
                "daily_change": 1.0,
                "daily_change_percent": 1.0,
                "bid_price": None,
                "ask_price": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "previous_close": 99.0,
                "day_high": 101.0,
                "day_low": 98.0,
                "fifty_two_week_high": 120.0,
                "fifty_two_week_low": 80.0,
                "market_status": "REGULAR",
                "last_update_time": "2026-03-20T15:30:00Z",
                "currency": "USD",
            },
            "MSFT": {
                "ticker": "MSFT",
                "current_price": 200.0,
                "daily_change": -2.0,
                "daily_change_percent": -1.0,
                "bid_price": None,
                "ask_price": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "previous_close": 202.0,
                "day_high": 205.0,
                "day_low": 198.0,
                "fifty_two_week_high": 240.0,
                "fifty_two_week_low": 160.0,
                "market_status": "REGULAR",
                "last_update_time": "2026-03-20T15:30:00Z",
                "currency": "USD",
            },
        }
        mock_gateway.get_company_info_batch.return_value = {
            "AAPL": {"name": "Apple Inc."},
            "MSFT": {"name": "Microsoft Corp."},
        }
        mock_gateway.get_latest_widget_data_for_tickers.return_value = {}

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway):
            client = TestClient(app)
            response = client.get("/api/tickers/widgets", params={"latest_analyzed": "true", "limit": 10, "include_events": "false"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual([widget["ticker"] for widget in payload["widgets"]], ["MSFT", "AAPL"])
        mock_gateway.get_latest_analyzed_tickers_paginated.assert_called_once_with(10, 0)

    def test_widgets_endpoint_skips_event_summary_work_when_events_disabled(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quotes_batch.return_value = {
            "AAPL": {
                "ticker": "AAPL",
                "current_price": 100.0,
                "daily_change": 1.0,
                "daily_change_percent": 1.0,
                "bid_price": None,
                "ask_price": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "previous_close": 99.0,
                "day_high": 101.0,
                "day_low": 98.0,
                "fifty_two_week_high": 120.0,
                "fifty_two_week_low": 80.0,
                "market_status": "REGULAR",
                "last_update_time": "2026-03-20T15:30:00Z",
                "currency": "USD",
            }
        }
        mock_gateway.get_company_info_batch.return_value = {"AAPL": {"name": "Apple Inc."}}
        mock_gateway.get_latest_widget_data_for_tickers.return_value = {}

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway), patch(
            "routers.tickers.get_cached_ticker_event_summary",
        ) as mock_get_cached_summary, patch(
            "routers.tickers.warm_ticker_event_summary_async",
        ) as mock_warm_summary:
            client = TestClient(app)
            response = client.get("/api/tickers/widgets", params={"tickers": "AAPL", "include_events": "false"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["widgets"]), 1)
        widget = payload["widgets"][0]
        self.assertIsNone(widget["dominant_events"])
        self.assertIsNone(widget["event_count"])
        mock_get_cached_summary.assert_not_called()
        mock_warm_summary.assert_not_called()

    def test_widgets_endpoint_does_not_block_on_event_summary_cache_miss(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quotes_batch.return_value = {
            "AAPL": {
                "ticker": "AAPL",
                "current_price": 100.0,
                "daily_change": 1.0,
                "daily_change_percent": 1.0,
                "bid_price": None,
                "ask_price": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "previous_close": 99.0,
                "day_high": 101.0,
                "day_low": 98.0,
                "fifty_two_week_high": 120.0,
                "fifty_two_week_low": 80.0,
                "market_status": "REGULAR",
                "last_update_time": "2026-03-20T15:30:00Z",
                "currency": "USD",
            }
        }
        mock_gateway.get_company_info_batch.return_value = {
            "AAPL": {"name": "Apple Inc."}
        }
        mock_gateway.get_quote.return_value = mock_gateway.get_quotes_batch.return_value["AAPL"]
        mock_gateway.get_latest_widget_data_for_tickers.return_value = {}

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway), patch(
            "routers.tickers.get_cached_ticker_event_summary",
            return_value=None,
        ) as mock_get_cached_summary, patch(
            "routers.tickers.warm_ticker_event_summary_async",
            return_value=True,
        ) as mock_warm_summary:
            client = TestClient(app)
            response = client.get("/api/tickers/widgets", params={"tickers": "AAPL"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["widgets"]), 1)
        widget = payload["widgets"][0]
        self.assertEqual(widget["ticker"], "AAPL")
        self.assertIsNone(widget["dominant_events"])
        self.assertIsNone(widget["event_count"])
        mock_get_cached_summary.assert_called_once()
        mock_warm_summary.assert_called_once()

    def test_widgets_endpoint_uses_cached_event_summary_when_available(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quotes_batch.return_value = {
            "AAPL": {
                "ticker": "AAPL",
                "current_price": 100.0,
                "daily_change": 1.0,
                "daily_change_percent": 1.0,
                "bid_price": None,
                "ask_price": None,
                "bid_size": None,
                "ask_size": None,
                "volume": None,
                "previous_close": 99.0,
                "day_high": 101.0,
                "day_low": 98.0,
                "fifty_two_week_high": 120.0,
                "fifty_two_week_low": 80.0,
                "market_status": "REGULAR",
                "last_update_time": "2026-03-20T15:30:00Z",
                "currency": "USD",
            }
        }
        mock_gateway.get_company_info_batch.return_value = {
            "AAPL": {"name": "Apple Inc."}
        }
        mock_gateway.get_quote.return_value = mock_gateway.get_quotes_batch.return_value["AAPL"]
        mock_gateway.get_latest_widget_data_for_tickers.return_value = {}

        mock_summary = MagicMock()
        mock_summary.dominant_events = ["price_spike_up", "volume_spike", "new_52w_high", "earnings_upcoming"]
        mock_summary.event_count = 4

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway), patch(
            "routers.tickers.get_cached_ticker_event_summary",
            return_value=mock_summary,
        ) as mock_get_cached_summary, patch(
            "routers.tickers.warm_ticker_event_summary_async",
            return_value=True,
        ) as mock_warm_summary:
            client = TestClient(app)
            response = client.get("/api/tickers/widgets", params={"tickers": "AAPL"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["widgets"]), 1)
        widget = payload["widgets"][0]
        self.assertEqual(widget["dominant_events"], ["price_spike_up", "volume_spike", "new_52w_high"])
        self.assertEqual(widget["event_count"], 4)
        mock_get_cached_summary.assert_called_once()
        mock_warm_summary.assert_not_called()

    def test_event_summaries_endpoint_returns_batch_payload(self) -> None:
        mock_gateway = MagicMock()

        aapl_summary = MagicMock()
        aapl_summary.dominant_events = ["price_spike_up", "volume_spike", "new_52w_high", "earnings_upcoming"]
        aapl_summary.event_count = 4

        msft_summary = MagicMock()
        msft_summary.dominant_events = ["earnings_upcoming"]
        msft_summary.event_count = 1

        def summary_side_effect(_gw, ticker, **_kwargs):
            return {"AAPL": aapl_summary, "MSFT": msft_summary}[ticker]

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway), patch(
            "routers.tickers.get_ticker_event_summary",
            side_effect=summary_side_effect,
        ):
            client = TestClient(app)
            response = client.get("/api/tickers/event-summaries", params={"tickers": "AAPL,MSFT"})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["summaries"]["AAPL"]["dominant_events"], ["price_spike_up", "volume_spike", "new_52w_high"])
        self.assertEqual(payload["summaries"]["AAPL"]["event_count"], 4)
        self.assertEqual(payload["summaries"]["MSFT"]["dominant_events"], ["earnings_upcoming"])
        self.assertEqual(payload["summaries"]["MSFT"]["event_count"], 1)

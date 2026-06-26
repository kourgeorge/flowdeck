from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.tickers import _get_ticker_page_sync, router as tickers_router


app = FastAPI()
app.include_router(tickers_router)


def _quote_payload(ticker: str = "AAPL") -> dict:
    return {
        "ticker": ticker,
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


def _valuation_report_payload() -> dict:
    return {
        "content": "Valuation body",
        "score": 9,
        "score_label": "Attractive",
        "key_takeaways": ["Base case upside remains compelling"],
        "analysis_date": "2026-06-26",
        "generated_at": "2026-06-26T11:00:00Z",
        "days_ago": 0,
        "models_used": {"provider": "openai"},
        "current_price": 100.0,
        "currency": "USD",
        "fair_value_bear": 85.0,
        "fair_value_base": 125.0,
        "fair_value_bull": 160.0,
        "current_discount_pct": 25.0,
        "valuation_conviction": "high",
        "valuation_key_assumptions": ["Revenue grows 8%"],
        "valuation_summary": {
            "method_weights": {"dcf": 0.5, "pe_comps": 0.3, "ev_ebitda": 0.2},
            "weighted_avg": {
                "bear": 85.0,
                "base": 125.0,
                "bull": 160.0,
                "weight": 1.0,
                "implied_value": 125.0,
            },
        },
        "valuation_bridge": {
            "current_price": 100.0,
            "growth_premium": 20.0,
            "multiple_expansion": 10.0,
            "risk_discount": -5.0,
            "fair_value": 125.0,
        },
        "valuation_sensitivity": {
            "wacc": {"delta": 0.01, "low": 115.0, "high": 135.0},
        },
        "dcf": {"base": 130.0},
        "pe_comps": {"base": 120.0},
        "ev_ebitda": {"base": 118.0},
    }


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

    def test_ticker_page_preserves_structured_valuation_report_metadata(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quote.return_value = _quote_payload()
        mock_gateway.get_latest_execution_for_ticker.return_value = (123, "2026-06-26")
        mock_gateway.get_reports_for_run.return_value = {"valuation_report": "Valuation body"}
        mock_gateway.get_reports_with_scores.return_value = {
            "valuation_report": _valuation_report_payload()
        }
        mock_gateway.get_historical_analyses.return_value = []

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway), patch(
            "routers.tickers.get_share_url",
            return_value="https://example.test/share/abc",
        ):
            payload = _get_ticker_page_sync("AAPL")

        valuation = payload.reports_with_scores["valuation_report"]
        self.assertEqual(valuation.fair_value_base, 125.0)
        self.assertEqual(valuation.current_discount_pct, 25.0)
        self.assertEqual(valuation.valuation_conviction, "high")
        self.assertEqual(valuation.valuation_key_assumptions, ["Revenue grows 8%"])
        self.assertEqual(valuation.valuation_summary["method_weights"]["dcf"], 0.5)
        self.assertEqual(valuation.valuation_bridge["fair_value"], 125.0)
        self.assertEqual(valuation.valuation_sensitivity["wacc"]["high"], 135.0)
        self.assertEqual(valuation.dcf, {"base": 130.0})

    def test_historical_report_endpoint_preserves_structured_valuation_metadata(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_reports_with_scores.return_value = {
            "valuation_report": _valuation_report_payload()
        }

        with patch("routers.tickers.get_data_gateway", return_value=mock_gateway):
            client = TestClient(app)
            response = client.get("/api/tickers/AAPL/reports/123")

        self.assertEqual(response.status_code, 200, response.text)
        valuation = response.json()["valuation_report"]
        self.assertEqual(valuation["fair_value_base"], 125.0)
        self.assertEqual(valuation["current_discount_pct"], 25.0)
        self.assertEqual(valuation["valuation_summary"]["method_weights"]["dcf"], 0.5)
        self.assertEqual(valuation["valuation_bridge"]["fair_value"], 125.0)
        self.assertEqual(valuation["valuation_sensitivity"]["wacc"]["low"], 115.0)

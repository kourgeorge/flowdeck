from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.data_api import router as data_router

app = FastAPI()
app.include_router(data_router)


class TestDeterministicEventsAPI(unittest.TestCase):
    def test_events_endpoint_forwards_lookback_days(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quote.return_value = {"current_price": 100.0}

        mock_summary = MagicMock()
        mock_summary.model_dump.return_value = {
            "ticker": "AAPL",
            "event_score": 2.0,
            "events": [],
            "dominant_events": ["price_spike_up"],
            "event_count": 1,
        }

        with patch("routers.data_api.get_data_gateway", return_value=mock_gateway), patch(
            "backend.processing.get_ticker_event_summary",
            return_value=mock_summary,
        ) as mock_get_ticker_event_summary:
            client = TestClient(app)
            response = client.get("/api/data/events/AAPL", params={"lookback_days": 15})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["ticker"], "AAPL")
        mock_get_ticker_event_summary.assert_called_once()
        call_args, call_kwargs = mock_get_ticker_event_summary.call_args
        self.assertEqual(call_args[0], mock_gateway)
        self.assertEqual(call_args[1], "AAPL")
        self.assertEqual(call_kwargs["price_technical_lookback_days"], 15)


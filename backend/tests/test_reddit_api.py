"""
Test Reddit company social API endpoint (GET /api/data/reddit-company-social/{ticker}).
Uses a minimal FastAPI app with only the data router to avoid loading main.py (TradingAgentsGraph).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.data_api import router as data_router

app = FastAPI()
app.include_router(data_router)


class TestRedditCompanySocialAPI(unittest.TestCase):
    """Verify reddit-company-social endpoint returns 200 and expected shape when gateway is mocked."""

    def test_reddit_company_social_returns_200_and_data_key(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quote.return_value = {"current_price": 100.0}
        mock_gateway.get_reddit_company_social.return_value = "## AAPL Reddit\n\ntest content"

        with patch("routers.data_api.get_data_gateway", return_value=mock_gateway):
            client = TestClient(app)
            resp = client.get(
                "/api/data/reddit-company-social/AAPL",
                params={
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-15",
                    "search_terms": "Apple,AAPL",
                },
            )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("ticker", data)
        self.assertIn("data", data)
        self.assertEqual(data["ticker"], "AAPL")
        self.assertEqual(data["data"], "## AAPL Reddit\n\ntest content")
        mock_gateway.get_reddit_company_social.assert_called_once_with(
            "AAPL", "2025-01-01", "2025-01-15", ["Apple", "AAPL"]
        )

    def test_reddit_company_social_400_when_search_terms_empty(self) -> None:
        mock_gateway = MagicMock()
        mock_gateway.get_quote.return_value = {"current_price": 100.0}

        with patch("routers.data_api.get_data_gateway", return_value=mock_gateway):
            client = TestClient(app)
            resp = client.get(
                "/api/data/reddit-company-social/AAPL",
                params={"start_date": "2025-01-01", "end_date": "2025-01-15", "search_terms": "  ,  "},
            )
        self.assertEqual(resp.status_code, 400, resp.text)

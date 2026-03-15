"""
Tests for MarketDataLayer (backend/data_layer/market.py).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from data_layer.market import MarketDataLayer, _valid_price, _quote_to_item
from services.data_cache import clear_cache


def _full_quote(ticker: str) -> dict:
    """Quote with all fields (as returned by get_quote / ticker.info)."""
    return {
        "current_price": 395.55,
        "daily_change": -6.31,
        "daily_change_percent": -1.57,
        "bid_price": 395.21,
        "ask_price": 395.89,
        "bid_size": 100,
        "ask_size": 200,
        "volume": 26_350_249,
        "previous_close": 401.86,
        "day_high": 404.8,
        "day_low": 392.1,
        "fifty_two_week_high": 555.45,
        "fifty_two_week_low": 302.0,
    }


def _batch_quote(ticker: str) -> dict:
    """Quote with limited fields (as returned by get_quotes_batch / yf.download)."""
    return {
        "current_price": 395.55,
        "daily_change": -6.31,
        "daily_change_percent": -1.57,
        "volume": 26_350_249,
        "previous_close": 401.86,
        "bid_price": None,
        "ask_price": None,
        "day_high": None,
        "day_low": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
    }


class TestValidPrice(unittest.TestCase):
    def test_valid_price_accepts_positive_float(self) -> None:
        self.assertTrue(_valid_price(100.5))
        self.assertTrue(_valid_price(1))

    def test_valid_price_rejects_none_zero_nan(self) -> None:
        self.assertFalse(_valid_price(None))
        self.assertFalse(_valid_price(0))
        self.assertFalse(_valid_price(float("nan")))


class TestQuoteToItem(unittest.TestCase):
    def test_quote_to_item_with_quote(self) -> None:
        q = {"current_price": 100.5, "daily_change": 2.0, "daily_change_percent": 2.03}
        item = _quote_to_item("AAPL", "Apple", q)
        self.assertEqual(item["ticker"], "AAPL")
        self.assertEqual(item["name"], "Apple")
        self.assertEqual(item["price"], 100.5)
        self.assertEqual(item["change"], 2.0)
        self.assertEqual(item["changePercent"], 2.03)

    def test_quote_to_item_with_none(self) -> None:
        item = _quote_to_item("AAPL", "Apple", None)
        self.assertEqual(item["ticker"], "AAPL")
        self.assertEqual(item["price"], None)
        self.assertEqual(item["change"], None)
        self.assertEqual(item["changePercent"], None)


class TestMarketDataLayerQuote(unittest.TestCase):
    """Tests for get_quote and get_quotes_batch, including cache isolation."""

    def setUp(self) -> None:
        clear_cache()

    @patch("data_layer.market.quote_vendor.get_quote")
    @patch("data_layer.market.get_cached")
    def test_get_quote_uses_quote_full_cache_key(
        self, mock_get_cached: object, mock_get_quote: object
    ) -> None:
        """get_quote must use quote_full:{ticker} so batch cache does not override."""
        mock_get_cached.side_effect = lambda key, ttl, fetch: fetch()
        mock_get_quote.return_value = _full_quote("MSFT")

        layer = MarketDataLayer()
        result = layer.get_quote("MSFT")

        mock_get_quote.assert_called_once_with("MSFT")
        mock_get_cached.assert_called_once()
        call_args = mock_get_cached.call_args[0]
        self.assertEqual(call_args[0], "quote_full:MSFT")

    @patch("data_layer.market.quote_vendor.get_quote")
    @patch("data_layer.market.get_cached")
    def test_get_quote_returns_full_fields(
        self, mock_get_cached: object, mock_get_quote: object
    ) -> None:
        """get_quote returns bid/ask, day_high, day_low, 52-week range."""
        mock_get_cached.side_effect = lambda key, ttl, fetch: fetch()
        mock_get_quote.return_value = _full_quote("MSFT")

        layer = MarketDataLayer()
        result = layer.get_quote("MSFT")

        self.assertIsNotNone(result)
        self.assertEqual(result["current_price"], 395.55)
        self.assertEqual(result["bid_price"], 395.21)
        self.assertEqual(result["ask_price"], 395.89)
        self.assertEqual(result["day_high"], 404.8)
        self.assertEqual(result["day_low"], 392.1)
        self.assertEqual(result["fifty_two_week_high"], 555.45)
        self.assertEqual(result["fifty_two_week_low"], 302.0)

    @patch("data_layer.market.quote_vendor.get_quotes_batch")
    @patch("data_layer.market.get_cached_batch")
    def test_get_quotes_batch_uses_quote_cache_key(
        self, mock_get_cached_batch: object, mock_get_quotes_batch: object
    ) -> None:
        """get_quotes_batch uses quote:{ticker} (not quote_full)."""
        def passthrough(keys, batch_fn):
            return batch_fn([f"quote:{k}" for k in ["MSFT", "AAPL"]])

        mock_get_cached_batch.side_effect = passthrough
        mock_get_quotes_batch.return_value = {
            "MSFT": _batch_quote("MSFT"),
            "AAPL": _batch_quote("AAPL"),
        }

        layer = MarketDataLayer()
        result = layer.get_quotes_batch(["MSFT", "AAPL"])

        mock_get_quotes_batch.assert_called_once_with(["MSFT", "AAPL"])
        self.assertEqual(result["MSFT"]["current_price"], 395.55)
        self.assertEqual(result["AAPL"]["current_price"], 395.55)

    @patch("data_layer.market.quote_vendor.get_quote")
    @patch("data_layer.market.quote_vendor.get_quotes_batch")
    @patch("data_layer.market.get_cached")
    @patch("data_layer.market.get_cached_batch")
    def test_batch_then_single_quote_returns_full_data(
        self,
        mock_get_cached_batch: object,
        mock_get_cached: object,
        mock_get_quotes_batch: object,
        mock_get_quote: object,
    ) -> None:
        """After batch warm, get_quote still returns full data (cache keys are isolated)."""
        call_count = {"get_cached": 0, "get_cached_batch": 0}

        def cached_impl(key, ttl, fetch):
            call_count["get_cached"] += 1
            return fetch()

        def cached_batch_impl(key_ttl, batch_fn):
            call_count["get_cached_batch"] += 1
            keys = [k for k, _ in key_ttl]
            return batch_fn(keys)

        mock_get_cached.side_effect = cached_impl
        mock_get_cached_batch.side_effect = cached_batch_impl
        mock_get_quotes_batch.return_value = {"MSFT": _batch_quote("MSFT")}
        mock_get_quote.return_value = _full_quote("MSFT")

        layer = MarketDataLayer()

        # Simulate batch warm (homepage)
        batch_result = layer.get_quotes_batch(["MSFT"])
        self.assertEqual(batch_result["MSFT"]["day_high"], None)  # batch has no day_high

        # Single quote must fetch full data (quote_full: key, not quote:)
        single_result = layer.get_quote("MSFT")
        self.assertIsNotNone(single_result)
        self.assertEqual(single_result["day_high"], 404.8)
        self.assertEqual(single_result["bid_price"], 395.21)
        self.assertEqual(single_result["fifty_two_week_high"], 555.45)


class TestMarketDataLayerRedditCompanySocial(unittest.TestCase):
    """Tests for get_reddit_company_social (Reddit vendor)."""

    def setUp(self) -> None:
        clear_cache()

    @patch("data_layer.market.get_reddit_company_social_online")
    @patch("data_layer.market.get_cached")
    def test_get_reddit_company_social_returns_vendor_string(
        self, mock_get_cached: object, mock_reddit: object
    ) -> None:
        mock_get_cached.side_effect = lambda key, ttl, fetch: fetch()
        mock_reddit.return_value = "## AAPL Reddit (social), from 2025-01-01 to 2025-01-15:\n\n### Post title\n\nBody."

        layer = MarketDataLayer()
        result = layer.get_reddit_company_social(
            "AAPL", "2025-01-01", "2025-01-15", search_terms=["Apple", "AAPL"]
        )

        self.assertIsInstance(result, str)
        self.assertIn("AAPL", result)
        self.assertIn("Post title", result)
        mock_reddit.assert_called_once_with("AAPL", "2025-01-01", "2025-01-15", ["Apple", "AAPL"])
        call_args = mock_get_cached.call_args[0]
        self.assertEqual(
            call_args[0],
            "reddit_company_social:AAPL:2025-01-01:2025-01-15:AAPL,Apple",
        )

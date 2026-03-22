from __future__ import annotations

import unittest
from unittest.mock import patch

from data_layer.vendors.yahoo_query import get_similar_tickers


class TestSimilarTickers(unittest.TestCase):
    def test_similar_tickers_refresh_sparse_cached_fundamentals(self) -> None:
        major_tickers = ["AAPL", "MSFT"]
        sector_cache = {
            "AAPL": {
                "name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "quoteType": "EQUITY",
                "market_cap": 3_000_000_000_000,
            },
            "MSFT": {
                "name": "Microsoft Corporation",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "quote_type": "EQUITY",
                "market_cap": 2_800_000_000_000,
                "trailing_pe": None,
                "forward_pe": None,
                "trailing_eps": None,
                "forward_eps": None,
                "ebitda": None,
                "revenue": None,
                "profit_margin": None,
                "gross_margin": None,
                "operating_margin": None,
                "ebitda_margin": None,
                "beta": None,
                "dividend_yield": None,
                "fifty_two_week_high": None,
                "fifty_two_week_low": None,
                "target_mean_price": None,
                "recommendation_key": None,
            },
        }

        fresh_msft = {
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 2_800_000_000_000,
            "trailing_pe": 35.2,
            "forward_pe": 30.1,
            "trailing_eps": 11.8,
            "forward_eps": 12.9,
            "ebitda": 140_000_000_000,
            "revenue": 250_000_000_000,
            "profit_margin": 0.34,
            "gross_margin": 0.69,
            "operating_margin": 0.44,
            "ebitda_margin": 0.50,
            "beta": 0.91,
            "dividend_yield": 0.0075,
            "fifty_two_week_high": 468.35,
            "fifty_two_week_low": 309.45,
            "target_mean_price": 490.0,
            "recommendation_key": "buy",
        }

        with patch(
            "data_layer.vendors.yahoo_query._load_major_tickers_and_cache",
            return_value=(major_tickers, sector_cache),
        ), patch(
            "data_layer.vendors.yahoo_query.get_sector_info_batch",
            return_value={"MSFT": fresh_msft},
        ) as mock_get_sector_info_batch:
            response = get_similar_tickers(
                "AAPL",
                limit=10,
                offset=0,
                get_quotes_batch=lambda symbols: {
                    symbol: {"current_price": 420.5, "daily_change_percent": 1.25}
                    for symbol in symbols
                },
            )

        self.assertEqual(response["count"], 1)
        row = response["similar_tickers"][0]
        self.assertEqual(row["ticker"], "MSFT")
        self.assertEqual(row["current_price"], 420.5)
        self.assertEqual(row["change_percent"], 1.25)
        self.assertEqual(row["trailing_pe"], 35.2)
        self.assertEqual(row["ebitda"], 140_000_000_000)
        self.assertEqual(row["dividend_yield"], 0.0075)
        self.assertEqual(row["fifty_two_week_high"], 468.35)
        mock_get_sector_info_batch.assert_called_once_with(["MSFT"])


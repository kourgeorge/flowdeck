import unittest

from scripts.update_stock_lists import safe_ticker_update, validate_ticker_update


class TestUpdateStockListsSafety(unittest.TestCase):
    def test_validate_ticker_update_rejects_small_parse(self) -> None:
        errors = validate_ticker_update(
            "S&P 500",
            ["AAPL", "MSFT"],
            [f"T{i}" for i in range(500)],
            min_count=450,
        )

        self.assertTrue(any("expected at least 450" in error for error in errors))

    def test_safe_ticker_update_keeps_existing_list_on_destructive_parse(self) -> None:
        old_tickers = [f"T{i}" for i in range(100)]
        fetched_tickers = old_tickers[:50]

        result = safe_ticker_update(
            "NASDAQ-100",
            fetched_tickers,
            old_tickers,
            min_count=90,
        )

        self.assertEqual(result, old_tickers)

    def test_safe_ticker_update_allows_force_override(self) -> None:
        old_tickers = [f"T{i}" for i in range(100)]
        fetched_tickers = old_tickers[:50]

        result = safe_ticker_update(
            "NASDAQ-100",
            fetched_tickers,
            old_tickers,
            min_count=90,
            force=True,
        )

        self.assertEqual(result, fetched_tickers)


if __name__ == "__main__":
    unittest.main()

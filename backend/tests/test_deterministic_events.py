from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine.briefing_agent.context_builder import build_digest_context
from backend.processing import (
    extract_fundamental_events,
    extract_insider_events,
    extract_price_technical_events,
    get_ticker_event_summary,
)
from services.data_cache import clear_cache, init_cache


def _bars_from_closes(
    closes: list[float],
    *,
    start: date,
    default_volume: int = 100_000,
    latest_open: float | None = None,
    latest_high: float | None = None,
    latest_low: float | None = None,
    latest_volume: int | None = None,
) -> list[dict]:
    bars: list[dict] = []
    for idx, close in enumerate(closes):
        day = start + timedelta(days=idx)
        prev_close = closes[idx - 1] if idx > 0 else close
        open_price = prev_close if idx > 0 else close
        high_price = max(open_price, close) * 1.005
        low_price = min(open_price, close) * 0.995
        volume = default_volume
        if idx == len(closes) - 1:
            if latest_open is not None:
                open_price = latest_open
            if latest_high is not None:
                high_price = latest_high
            if latest_low is not None:
                low_price = latest_low
            if latest_volume is not None:
                volume = latest_volume
        bars.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close, 2),
                "volume": volume,
            }
        )
    return bars


class _ContextFetcher:
    def __init__(
        self,
        histories: dict[str, list[dict]],
        future_events: dict[str, dict],
        insider_transactions: dict[str, dict] | None = None,
    ):
        self._histories = histories
        self._future_events = future_events
        self._insider_transactions = insider_transactions or {}

    def get_daily_market_movers(self, limit: int) -> dict:
        return {}

    def get_quotes_batch(self, tickers: list[str]) -> dict:
        out = {}
        for ticker in tickers:
            bars = self._histories.get(ticker) or []
            last = bars[-1] if bars else {}
            out[ticker] = {
                "current_price": last.get("close"),
                "price": last.get("close"),
                "name": ticker,
            }
        return out

    def get_historical(self, ticker: str, period: str = "1y", interval: str = "1d") -> dict:
        return {"ticker": ticker, "period": period, "interval": interval, "data": self._histories.get(ticker, [])}

    def get_news_batch(self, tickers: list[str], lookback_days: int = 2) -> dict:
        return {"articles": [], "count": 0}

    def get_news(self, ticker: str, lookback_days: int = 7) -> dict:
        return {"articles": []}

    def get_fundamentals(self, ticker: str) -> dict:
        return {"ticker": ticker}

    def get_analyst_recommendations(self, ticker: str) -> dict:
        return {"ticker": ticker, "recommendation": "HOLD"}

    def get_insider_transactions(self, ticker: str, limit: int = 20) -> dict:
        return self._insider_transactions.get(ticker, {"ticker": ticker, "transactions": [], "count": 0})

    def get_future_events(self, ticker: str) -> dict:
        return self._future_events.get(ticker, {"ticker": ticker, "events": [], "count": 0})

    def get_indicators(self, ticker: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
        return ""

    def get_company_info_batch(self, tickers: list[str]) -> dict:
        return {ticker: {"sector": "Technology", "industry": "Software"} for ticker in tickers}


class _CountingEventFetcher:
    def __init__(self, bars: list[dict]):
        self._bars = bars
        self.calls = {
            "historical": 0,
            "future_events": 0,
            "insider_transactions": 0,
            "indicators": 0,
        }

    def get_historical(self, ticker: str, period: str = "1y", interval: str = "1d") -> dict:
        self.calls["historical"] += 1
        return {"ticker": ticker, "period": period, "interval": interval, "data": self._bars}

    def get_future_events(self, ticker: str) -> dict:
        self.calls["future_events"] += 1
        return {"ticker": ticker, "events": [], "count": 0}

    def get_insider_transactions(self, ticker: str, limit: int = 50) -> dict:
        self.calls["insider_transactions"] += 1
        return {"ticker": ticker, "transactions": [], "count": 0}

    def get_indicators(self, ticker: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
        self.calls["indicators"] += 1
        return ""


class TestDeterministicPriceEvents(unittest.TestCase):
    def test_extract_price_events_detects_high_confidence_signals(self) -> None:
        closes = [100.0 + 0.05 * i for i in range(259)] + [125.0]
        bars = _bars_from_closes(
            closes,
            start=date(2025, 1, 1),
            latest_open=120.0,
            latest_high=126.0,
            latest_low=119.5,
            latest_volume=350_000,
        )

        summary = extract_price_technical_events("AAPL", bars=bars)
        event_types = {event.event_type for event in summary.events}

        self.assertIn("price_spike_up", event_types)
        self.assertIn("price_gap_up", event_types)
        self.assertIn("new_52w_high", event_types)
        self.assertIn("volume_spike", event_types)
        self.assertGreater(summary.event_score, 0.0)

    def test_extract_price_events_detects_volatility_expansion(self) -> None:
        closes = [100.0 + (0.1 if i % 2 == 0 else -0.1) for i in range(70)]
        closes += [95.0, 105.0, 94.0, 106.0, 93.0, 107.0, 92.0, 108.0, 91.0, 109.0]
        bars = _bars_from_closes(closes, start=date(2025, 1, 1))

        summary = extract_price_technical_events("NVDA", bars=bars)
        event_types = {event.event_type for event in summary.events}

        self.assertIn("volatility_expansion", event_types)

    def test_extract_price_events_detects_moving_average_cross(self) -> None:
        closes = [100.0] * 49 + [130.0]
        bars = _bars_from_closes(closes, start=date(2025, 1, 1))

        summary = extract_price_technical_events("MSFT", bars=bars)
        cross_events = [event for event in summary.events if event.event_type == "moving_average_cross"]

        self.assertEqual(len(cross_events), 1)
        self.assertEqual(cross_events[0].metadata.get("cross"), "bullish")


class TestTickerEventProcessingService(unittest.TestCase):
    def setUp(self) -> None:
        init_cache(maxsize=1024)
        clear_cache()

    def test_get_ticker_event_summary_uses_processing_cache(self) -> None:
        closes = [100.0 + 0.05 * i for i in range(259)] + [125.0]
        bars = _bars_from_closes(
            closes,
            start=date(2025, 1, 1),
            latest_open=120.0,
            latest_high=126.0,
            latest_low=119.5,
            latest_volume=350_000,
        )
        fetcher = _CountingEventFetcher(bars)

        first = get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-19")
        second = get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-19")

        self.assertEqual(fetcher.calls["historical"], 1)
        self.assertEqual(fetcher.calls["future_events"], 1)
        self.assertEqual(fetcher.calls["insider_transactions"], 1)
        self.assertEqual(fetcher.calls["indicators"], 1)
        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertGreater(first.event_score, 0.0)


class TestDeterministicFundamentalEvents(unittest.TestCase):
    def test_extract_fundamental_events_detects_earnings_upcoming(self) -> None:
        summary = extract_fundamental_events(
            "AAPL",
            as_of_date="2026-03-19",
            future_events={
                "ticker": "AAPL",
                "events": [
                    {"date": "2026-03-25", "type": "earnings", "label": "Earnings", "eps_estimate": 1.42}
                ],
                "count": 1,
            },
        )

        self.assertEqual(summary.dominant_events, ["earnings_upcoming"])
        self.assertEqual(summary.events[0].event_type, "earnings_upcoming")
        self.assertEqual(summary.events[0].metadata.get("days_until"), 6)

    def test_extract_insider_events_detects_recent_selling(self) -> None:
        summary = extract_insider_events(
            "AAPL",
            as_of_date="2026-03-19",
            insider_transactions={
                "ticker": "AAPL",
                "transactions": [
                    {
                        "insider": "Jane Doe",
                        "transaction": "Sale",
                        "start_date": "2026-03-15",
                        "shares": 5000,
                        "value": 250000,
                    }
                ],
                "count": 1,
            },
        )

        self.assertEqual(summary.dominant_events, ["insider_selling"])
        self.assertEqual(summary.events[0].event_type, "insider_selling")
        self.assertEqual(summary.events[0].metadata.get("transaction_count"), 1)

    def test_extract_insider_events_detects_recent_selling_from_short_code(self) -> None:
        summary = extract_insider_events(
            "FROG",
            as_of_date="2026-03-19",
            insider_transactions={
                "ticker": "FROG",
                "transactions": [
                    {
                        "insider": "HAIM SHLOMI BEN",
                        "transaction": "D",
                        "start_date": "2026-03-06",
                        "shares": 25363,
                        "value": 1052661,
                    },
                    {
                        "insider": "SIMON FREDERIC",
                        "transaction": "D",
                        "start_date": "2026-03-03",
                        "shares": 35000,
                        "value": 1425300,
                    },
                ],
                "count": 2,
            },
        )

        self.assertEqual(summary.dominant_events, ["insider_selling"])
        self.assertEqual(summary.events[0].event_type, "insider_selling")
        self.assertEqual(summary.events[0].metadata.get("transaction_count"), 2)

    def test_extract_insider_events_detects_recent_selling_from_text_when_transaction_blank(self) -> None:
        summary = extract_insider_events(
            "FROG",
            as_of_date="2026-03-19",
            insider_transactions={
                "ticker": "FROG",
                "transactions": [
                    {
                        "insider": "HAIM SHLOMI BEN",
                        "transaction": "",
                        "text": "Sale at price 41.05 - 41.84 per share.",
                        "start_date": "2026-03-06",
                        "shares": 25363,
                        "value": 1052661,
                    },
                    {
                        "insider": "SIMON FREDERIC",
                        "transaction": "",
                        "text": "Sale at price 40.18 - 42.08 per share.",
                        "start_date": "2026-03-03",
                        "shares": 35000,
                        "value": 1425300,
                    },
                ],
                "count": 2,
            },
        )

        self.assertEqual(summary.dominant_events, ["insider_selling"])
        self.assertEqual(summary.events[0].event_type, "insider_selling")
        self.assertEqual(summary.events[0].metadata.get("transaction_count"), 2)


class TestDigestContextEventIntegration(unittest.TestCase):
    @patch("ai_engine.briefing_agent.context_builder._fetch_web_snippet", return_value=None)
    @patch("ai_engine.briefing_agent.context_builder._fetch_global_news", return_value=None)
    @patch("ai_engine.briefing_agent.context_builder._get_user_context_snapshot", return_value="Long-term investor")
    @patch("ai_engine.briefing_agent.context_builder._load_portfolio_tickers", return_value=["AAPL", "MSFT"])
    @patch("services.share_service.get_share_url", return_value=None)
    @patch("services.report_service.ReportService")
    def test_build_digest_context_populates_event_summaries_and_uses_event_scores(
        self,
        mock_report_service,
        _mock_share_url,
        _mock_tickers,
        _mock_user_context,
        _mock_global_news,
        _mock_web_snippet,
    ) -> None:
        aapl_closes = [100.0 + 0.05 * i for i in range(259)] + [125.0]
        msft_closes = [100.0 + 0.02 * i for i in range(260)]
        histories = {
            "AAPL": _bars_from_closes(
                aapl_closes,
                start=date(2025, 1, 1),
                latest_open=120.0,
                latest_high=126.0,
                latest_low=119.5,
                latest_volume=350_000,
            ),
            "MSFT": _bars_from_closes(msft_closes, start=date(2025, 1, 1)),
        }
        future_events = {
            "AAPL": {
                "ticker": "AAPL",
                "events": [{"date": "2026-03-25", "type": "earnings", "label": "Earnings", "eps_estimate": 1.42}],
                "count": 1,
            },
            "MSFT": {"ticker": "MSFT", "events": [], "count": 0},
        }
        insider_transactions = {
            "AAPL": {
                "ticker": "AAPL",
                "transactions": [
                    {
                        "insider": "Jane Doe",
                        "transaction": "Purchase",
                        "start_date": "2026-03-18",
                        "shares": 4000,
                        "value": 160000,
                    }
                ],
                "count": 1,
            },
            "MSFT": {"ticker": "MSFT", "transactions": [], "count": 0},
        }
        mock_report_service.return_value.get_latest_execution_for_ticker.return_value = None

        result = build_digest_context(
            user_id=7,
            digest_date="2026-03-19",
            max_priority_tickers=2,
            db=object(),
            fetcher=_ContextFetcher(histories, future_events, insider_transactions),
        )

        self.assertIn("AAPL", result.event_summaries)
        self.assertGreater(result.event_scores["AAPL"], result.event_scores["MSFT"])
        self.assertEqual(result.priority_tickers[0], "AAPL")
        self.assertIn("earnings_upcoming", {event.event_type for event in result.event_summaries["AAPL"].events})
        self.assertIn("insider_buying", {event.event_type for event in result.event_summaries["AAPL"].events})


if __name__ == "__main__":
    unittest.main()

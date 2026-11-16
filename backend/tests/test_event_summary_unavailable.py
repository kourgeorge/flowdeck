"""A failed price-history load must read as "unavailable", never as a quiet ticker.

The gaps-bot scout found a fetcher raising TimeoutError produced a cached
{'event_score': 0.0, 'events': []} with no error, which every caller (agents triaging via
/api/data/events, the morning event monitor) took for "nothing happening".
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_engine.processing import service


def _quiet_bars(n: int = 60):
    # Tiny alternating moves on flat volume: loads fine, triggers no event rule.
    start = date(2026, 1, 1)
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "open": 100 + (i % 2) * 0.1,
            "high": 100.5 + (i % 2) * 0.1,
            "low": 99.5 + (i % 2) * 0.1,
            "close": 100 + (i % 2) * 0.1,
            "volume": 1_000_000,
        }
        for i in range(n)
    ]


class _Fetcher:
    def __init__(self, *, raises=None, bars=None):
        self.raises = raises
        self.bars = bars
        self.history_calls = 0

    def get_historical(self, ticker, period, interval):
        self.history_calls += 1
        if self.raises is not None:
            raise self.raises
        return {"data": self.bars}

    def get_insider_transactions(self, ticker, limit):
        return {}


def _dict_cache(monkeypatch):
    """Swap in a plain dict cache that, like the backend one, doesn't store exceptions."""
    store = {}

    def get_or_set(namespace, *, parts, ttl_seconds, fetch_fn, version):
        key = ":".join([namespace, version, *(str(p) for p in parts)])
        if key not in store:
            store[key] = fetch_fn()
        return store[key]

    monkeypatch.setattr(
        service,
        "_cache",
        {
            "get_or_set": get_or_set,
            "get_cached_raw": store.get,
            "make_cache_key": lambda ns, *parts, version: ":".join([ns, version, *(str(p) for p in parts)]),
            "ttl_seconds": 600,
        },
    )
    return store


def test_fetch_error_gives_no_score_and_an_error(monkeypatch):
    _dict_cache(monkeypatch)
    fetcher = _Fetcher(raises=TimeoutError("vendor timed out"))

    summary = service.get_ticker_event_summary(fetcher, "aapl", as_of_date="2026-03-01")

    assert summary.ticker == "AAPL"
    assert summary.event_score is None
    assert summary.available is False
    assert "TimeoutError" in summary.error
    assert summary.events == []


def test_unavailable_result_is_not_cached(monkeypatch):
    store = _dict_cache(monkeypatch)
    fetcher = _Fetcher(raises=TimeoutError("vendor timed out"))

    service.get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-01")
    service.get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-01")

    assert fetcher.history_calls == 2
    assert store == {}

    # Once the vendor recovers, the real result is computed and cached as usual.
    fetcher.raises = None
    fetcher.bars = _quiet_bars()
    recovered = service.get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-01")
    assert recovered.event_score == 0.0 and recovered.available
    assert len(store) == 1


def test_no_bars_at_all_is_unavailable(monkeypatch):
    _dict_cache(monkeypatch)
    fetcher = _Fetcher(bars=[])

    summary = service.get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-01")

    assert summary.event_score is None
    assert summary.available is False
    assert summary.error


def test_loaded_quiet_history_still_scores_zero(monkeypatch):
    _dict_cache(monkeypatch)
    fetcher = _Fetcher(bars=_quiet_bars())

    summary = service.get_ticker_event_summary(fetcher, "AAPL", as_of_date="2026-03-01")

    assert summary.event_score == 0.0
    assert summary.available is True
    assert summary.error is None
    assert summary.event_count == 0


def test_data_api_error_path_returns_no_score():
    from routers.data_api import router as data_router

    app = FastAPI()
    app.include_router(data_router)
    gateway = MagicMock()
    gateway.get_quote.return_value = {"current_price": 100.0}

    with patch("routers.data_api.get_data_gateway", return_value=gateway), patch(
        "backend.processing.get_ticker_event_summary", side_effect=RuntimeError("boom")
    ):
        response = TestClient(app).get("/api/data/events/AAPL")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["event_score"] is None
    assert body["available"] is False
    assert body["error"] == "boom"


def test_analysis_does_not_stamp_an_unavailable_score():
    from services import analysis_report_helpers

    unavailable = service._unavailable_summary("AAPL", "Price history could not be loaded: no bars returned.")
    with patch("data_layer.get_data_gateway", return_value=object()), patch(
        "processing.get_ticker_event_summary", return_value=unavailable
    ):
        meta = analysis_report_helpers.get_analysis_event_meta("AAPL", "2026-03-01")

    assert meta == {}


def test_chat_events_tool_says_unavailable(monkeypatch):
    from ai_engine.agent.tools import events as events_tool

    unavailable = service._unavailable_summary("AAPL", "Price history could not be loaded: TimeoutError: slow")
    with patch("data_layer.get_data_gateway", return_value=object()), patch(
        "ai_engine.processing.get_ticker_event_summary", return_value=unavailable
    ):
        text = events_tool._fetch_events("AAPL")

    assert "unavailable" in text.lower()
    assert "TimeoutError" in text
    assert "No active events were detected" not in text

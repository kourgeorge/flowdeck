"""/api/tickers/event-summaries must not turn a ticker we could not score into "0 tracked"."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.tickers as tickers_module
from processing.event import TickerEventSummary


def _client(monkeypatch, fake_summary) -> TestClient:
    monkeypatch.setattr(tickers_module, "get_data_gateway", lambda: object())
    monkeypatch.setattr(tickers_module, "get_ticker_event_summary", fake_summary)
    app = FastAPI()
    app.include_router(tickers_module.router)
    return TestClient(app)


def test_unavailable_summary_gives_none_counts_not_zero(monkeypatch) -> None:
    def fake_summary(gw, ticker, *, as_of_date):
        # What ai_engine returns when price history can't be loaded (T-101).
        return TickerEventSummary(
            ticker=ticker,
            event_score=None,
            available=False,
            error="Price history could not be loaded: no bars returned.",
        )

    resp = _client(monkeypatch, fake_summary).get("/api/tickers/event-summaries?tickers=AAPL")

    assert resp.status_code == 200
    assert resp.json()["summaries"]["AAPL"] == {"dominant_events": None, "event_count": None}


def test_raising_summary_gives_none_counts_not_zero(monkeypatch) -> None:
    def fake_summary(gw, ticker, *, as_of_date):
        # The gaps-bot scout reproduced the "0 tracked" card with a gateway timing out.
        raise TimeoutError("gateway timed out")

    resp = _client(monkeypatch, fake_summary).get("/api/tickers/event-summaries?tickers=AAPL,MSFT")

    assert resp.status_code == 200
    summaries = resp.json()["summaries"]
    assert summaries["AAPL"] == {"dominant_events": None, "event_count": None}
    assert summaries["MSFT"] == {"dominant_events": None, "event_count": None}


def test_available_quiet_summary_still_reports_zero(monkeypatch) -> None:
    # A real "nothing happened" must stay 0 / [], so the None above means unknown only.
    def fake_summary(gw, ticker, *, as_of_date):
        return TickerEventSummary(ticker=ticker, event_score=0.0, available=True)

    resp = _client(monkeypatch, fake_summary).get("/api/tickers/event-summaries?tickers=AAPL")

    assert resp.status_code == 200
    assert resp.json()["summaries"]["AAPL"] == {"dominant_events": [], "event_count": 0}

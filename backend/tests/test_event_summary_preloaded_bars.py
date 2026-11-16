"""Empty preloaded price history must read as "unavailable", same as a failed fetch.

The daily brief and stocks discovery load history in bulk and pass
`ohlcv_history.get(t) or []`, so a ticker whose bulk load failed arrived as an empty
list and scored 0.0, which looked like a quiet ticker.
"""

from __future__ import annotations

from datetime import date, timedelta

from ai_engine.briefing_agent import agents as brief_agents
from ai_engine.briefing_agent.state import DigestContext
from ai_engine.processing import service
from ai_engine.stocks_discovery import deterministic


def _quiet_bars(n: int = 60):
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


class _NoFetchFetcher:
    """Any fetch means the preloaded inputs were ignored."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected fetch: {name}")


def _dict_cache(monkeypatch):
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


def _summary(bars):
    return service.get_ticker_event_summary(
        _NoFetchFetcher(),
        "aapl",
        as_of_date="2026-03-01",
        bars=bars,
        future_events={},
        insider_transactions={},
        rsi_data={},
    )


def test_empty_preloaded_bars_are_unavailable_and_not_cached(monkeypatch):
    store = _dict_cache(monkeypatch)

    summary = _summary([])

    assert summary.event_score is None
    assert summary.available is False
    assert "could not be loaded" in summary.error
    assert store == {}


def test_quiet_preloaded_history_scores_zero(monkeypatch):
    _dict_cache(monkeypatch)

    summary = _summary(_quiet_bars())

    assert summary.event_score == 0.0
    assert summary.available is True
    assert summary.error is None


def test_brief_ticker_context_says_unavailable_not_quiet():
    unavailable = service._unavailable_summary("AAPL", "Price history could not be loaded: no bars provided.")
    ctx = DigestContext(tickers=["AAPL"], event_summaries={"AAPL": unavailable}, event_scores={"AAPL": None})

    text = brief_agents._format_ticker_context(ctx, "AAPL")

    assert "unavailable" in text.lower()
    assert "Deterministic event score: 0" not in text


def test_discovery_ranking_handles_none_score(monkeypatch):
    scores = {"AAA": None, "BBB": 2.5, "CCC": 0.0}

    def fake_summary(fetcher, ticker, **kwargs):
        score = scores[ticker]
        if score is None:
            return service._unavailable_summary(ticker, "Price history could not be loaded: no bars provided.")
        return service.TickerEventSummary(ticker=ticker, event_score=score)

    monkeypatch.setattr(deterministic, "get_ticker_event_summary", fake_summary)
    for name in ("_load_ohlcv_history", "_load_future_events", "_load_insider_transactions", "_load_rsi_maps"):
        monkeypatch.setattr(deterministic, name, lambda *a, **k: {})

    class _Fetcher:
        def get_company_info_batch(self, tickers):
            return {}

        def get_quotes_batch(self, tickers):
            return {}

    top, summaries, _info = deterministic._score_tickers_by_event_activity(
        ["AAA", "BBB", "CCC"], _Fetcher(), "2026-03-01"
    )

    assert top == ["BBB"]
    assert summaries["AAA"].event_score is None

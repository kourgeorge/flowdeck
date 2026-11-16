"""Daily Brief Polymarket context: event probabilities only, fetched over HTTP (T-48)."""

import re
from pathlib import Path

from ai_engine.briefing_agent import context_builder, prompts
from ai_engine.briefing_agent.agents import _format_ticker_context
from ai_engine.briefing_agent.state import DigestContext
from ai_engine.tradingagents.datasources import info_service_client

BRIEFING_DIR = Path(__file__).resolve().parents[2] / "ai_engine" / "briefing_agent"


def _payload():
    # Shape of /api/polymarket/ticker/{ticker}: the service never infers a trend.
    return {
        "ticker": "NVDA",
        "overall_sentiment": None,
        "confidence": None,
        "trend": "unknown",
        "market_count": 2,
        "top_markets": [
            {"question": "Will NVDA hit $200 by June?", "probability": 0.42, "change_24h": 0.03, "volume": 125000},
            {"question": "Will chip export rules tighten?", "probability": None, "change_24h": None, "volume": None},
        ],
        "error": None,
    }


def test_fetch_uses_info_service_client(monkeypatch):
    calls = []

    def fake_get(ticker, base_url=None):
        calls.append(ticker)
        return _payload() if ticker == "NVDA" else {"error": "no markets", "top_markets": []}

    monkeypatch.setattr(info_service_client, "get_polymarket_sentiment", fake_get)
    out = context_builder._fetch_polymarket_markets(["NVDA", "XYZ"])
    assert calls == ["NVDA", "XYZ"]
    assert list(out) == ["NVDA"]
    assert out["NVDA"]["top_markets"][0]["probability"] == 0.42


def test_ticker_context_shows_markets_without_trend():
    ctx = DigestContext(tickers=["NVDA"], polymarket_markets={"NVDA": _payload()})
    text = _format_ticker_context(ctx, "NVDA")
    assert "trend=" not in text
    assert "sentiment_score" not in text
    assert "Will NVDA hit $200 by June? [prob=42%, 24h_change=+3.0pp, vol=$125,000]" in text
    assert "Will chip export rules tighten? [prob=n/a, 24h_change=n/a]" in text


def test_prompt_does_not_promise_sentiment_score():
    text = prompts.TICKER_INTERPRETER_SYSTEM.lower()
    assert "sentiment score" not in text
    assert "0–1" not in text
    assert "bullish/neutral/bearish" not in text
    assert "contrarian or confirmatory" not in text


def test_briefing_agent_does_not_import_backend_polymarket_service():
    pattern = re.compile(r"^\s*(from|import)\s+services\.polymarket_service", re.M)
    for path in BRIEFING_DIR.rglob("*.py"):
        assert not pattern.search(path.read_text()), path

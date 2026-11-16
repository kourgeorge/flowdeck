"""The get_market_rates LLM tool must not invent yields when the info service fails.

It used to answer None from info_service_client with 0.045/0.045/0.045/0.05,
which the analyst then quoted as current FRED data.
"""

import json

from ai_engine.tradingagents.agents.utils import market_rates_tools


def _call_tool(monkeypatch, service_result):
    monkeypatch.setattr(market_rates_tools, "require_info_service", lambda: None)
    monkeypatch.setattr(
        market_rates_tools, "get_market_rates_via_service", lambda: service_result
    )
    return json.loads(market_rates_tools.get_market_rates.invoke({}))


def test_service_unavailable_returns_null_rates(monkeypatch):
    out = _call_tool(monkeypatch, None)

    assert out["source"] == "unavailable"
    for field in ("risk_free_rate", "treasury_10y", "treasury_2y", "treasury_3m"):
        assert out[field] is None
    assert all(v is None for v in out["field_sources"].values())
    assert "could not be fetched" in out["note"]
    values = [v for v in out.values() if isinstance(v, (int, float))]
    assert 0.045 not in values and 0.05 not in values


def test_partial_data_passes_through(monkeypatch):
    partial = {
        "risk_free_rate": 0.0431,
        "treasury_10y": 0.0431,
        "treasury_2y": None,
        "treasury_3m": 0.0402,
        "vix": None,
        "market_risk_premium": 0.05,
        "last_updated": "2026-11-16T10:00:00+00:00",
        "source": "partial",
        "field_sources": {
            "risk_free_rate": "FRED",
            "treasury_10y": "FRED",
            "treasury_2y": None,
            "treasury_3m": "FRED",
            "vix": None,
            "market_risk_premium": "historical_average_assumption",
        },
        "cache_age_hours": 0.0,
    }
    out = _call_tool(monkeypatch, partial)

    assert out == partial
    assert out["treasury_2y"] is None
    assert out["field_sources"]["treasury_2y"] is None


def test_full_fred_data_passes_through(monkeypatch):
    full = {
        "risk_free_rate": 0.0466,
        "treasury_10y": 0.0466,
        "treasury_2y": 0.0419,
        "treasury_3m": 0.0385,
        "vix": 15.21,
        "market_risk_premium": 0.0501,
        "last_updated": "2026-08-28T11:12:08+00:00",
        "source": "FRED",
        "field_sources": {
            "risk_free_rate": "FRED",
            "treasury_10y": "FRED",
            "treasury_2y": "FRED",
            "treasury_3m": "FRED",
            "vix": "yfinance",
            "market_risk_premium": "derived_from_vix",
        },
        "cache_age_hours": 1.5,
    }
    assert _call_tool(monkeypatch, full) == full

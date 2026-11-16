"""FRED failures must not be labelled as FRED, guessed, or cached for a day."""

from datetime import timedelta

import pytest
import requests

from services import market_rates_service as mrs
from services.market_rates_service import MarketRatesService


class _FakeResponse:
    def __init__(self, value):
        self._value = value

    def raise_for_status(self):
        pass

    def json(self):
        return {"observations": [{"date": "2026-11-13", "value": self._value}]}


def _setup(monkeypatch, values):
    """values maps FRED series id -> raw percent string; missing ids time out."""
    monkeypatch.setattr(mrs, "FRED_API_KEY", "test-key")
    monkeypatch.setattr(MarketRatesService, "_fetch_vix_from_yfinance", classmethod(lambda cls: None))

    def fake_get(url, params=None, timeout=None):
        series = params["series_id"]
        if series not in values:
            raise requests.exceptions.Timeout(f"{series} timed out")
        return _FakeResponse(values[series])

    monkeypatch.setattr(mrs.requests, "get", fake_get)
    MarketRatesService.clear_cache()


def test_all_fred_calls_time_out(monkeypatch):
    _setup(monkeypatch, {})
    rates = MarketRatesService.get_market_rates(force_refresh=True)

    assert rates["source"] == "unavailable"
    for field in ("risk_free_rate", "treasury_10y", "treasury_2y", "treasury_3m", "vix"):
        assert rates[field] is None
        assert rates["field_sources"][field] is None
    assert "FRED" not in rates["field_sources"].values()
    assert MarketRatesService._cache_ttl <= timedelta(minutes=15)
    MarketRatesService.clear_cache()


def test_partial_success_labels_only_returned_fields(monkeypatch):
    _setup(monkeypatch, {"DGS10": "4.30"})
    rates = MarketRatesService.get_market_rates(force_refresh=True)

    assert rates["source"] == "partial"
    assert rates["risk_free_rate"] == pytest.approx(0.043)
    assert rates["treasury_10y"] == pytest.approx(0.043)
    # Not filled in with the 10-year yield or a hard-coded default.
    assert rates["treasury_2y"] is None
    assert rates["treasury_3m"] is None
    fs = rates["field_sources"]
    assert fs["risk_free_rate"] == "FRED" and fs["treasury_10y"] == "FRED"
    assert fs["treasury_2y"] is None and fs["treasury_3m"] is None
    assert MarketRatesService._cache_ttl <= timedelta(minutes=15)
    MarketRatesService.clear_cache()


def test_full_success_is_fred_and_cached_for_a_day(monkeypatch):
    _setup(monkeypatch, {"DGS10": "4.30", "DGS2": "4.10", "DGS3MO": "3.90", "VIXCLS": "18.0"})
    rates = MarketRatesService.get_market_rates(force_refresh=True)

    assert rates["source"] == "FRED"
    assert rates["treasury_2y"] == pytest.approx(0.041)
    assert rates["treasury_3m"] == pytest.approx(0.039)
    assert rates["vix"] == 18.0
    assert all(rates["field_sources"][f] == "FRED" for f in ("risk_free_rate", "treasury_10y", "treasury_2y", "treasury_3m", "vix"))
    assert MarketRatesService._cache_ttl == timedelta(hours=24)

    # Served from cache: no more network calls.
    monkeypatch.setattr(mrs.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("refetched")))
    assert MarketRatesService.get_market_rates()["source"] == "FRED"
    MarketRatesService.clear_cache()


def test_valuation_labels_missing_risk_free_rate_as_assumption(monkeypatch):
    from ai_engine.tradingagents.agents.utils import valuation_tools as vt
    from ai_engine.tradingagents.datasources import info_service_client

    monkeypatch.setattr(info_service_client, "get_market_rates", lambda *a, **k: {"risk_free_rate": None, "source": "unavailable"})
    rate, label = vt._get_risk_free_rate_with_source()
    assert rate == 0.045
    assert label and "assumed" in label and "FRED" in label
    assert "not market data" in vt._risk_free_warning(label, rate)

    monkeypatch.setattr(info_service_client, "get_market_rates", lambda *a, **k: {"risk_free_rate": 0.043, "source": "FRED"})
    assert vt._get_risk_free_rate_with_source() == (pytest.approx(0.043), None)


def _etf_with_rates(monkeypatch, rates):
    from ai_engine.tradingagents.agents.utils import valuation_tools as vt
    from ai_engine.tradingagents.datasources import info_service_client

    monkeypatch.setattr(info_service_client, "get_market_rates", lambda *a, **k: rates)
    result = vt._build_index_etf_valuation(ticker="TEST", current_price=100, fundamentals={"QuoteType": "ETF", "ForwardPE": 20})
    premium_warnings = [line for line in result["valuation_key_assumptions"] if "Market risk premium" in line and "not market data" in line]
    return vt, result, premium_warnings


def test_valuation_flags_assumed_market_risk_premium_when_service_down(monkeypatch):
    vt, result, premium_warnings = _etf_with_rates(monkeypatch, None)
    assert vt._get_market_risk_premium_with_source() == (0.055, "assumed")
    assert result["inputs"]["market_risk_premium"] == 0.055
    assert result["inputs"]["market_risk_premium_source"] == "assumed"
    assert len(premium_warnings) == 1 and "5.50%" in premium_warnings[0]


def test_valuation_flags_service_historical_average_premium(monkeypatch):
    rates = {
        "risk_free_rate": 0.043,
        "market_risk_premium": 0.055,
        "field_sources": {"risk_free_rate": "FRED", "market_risk_premium": "historical_average_assumption"},
    }
    vt, result, premium_warnings = _etf_with_rates(monkeypatch, rates)
    assert result["inputs"]["market_risk_premium_source"] == "historical_average_assumption"
    assert len(premium_warnings) == 1 and "historical-average" in premium_warnings[0]


def test_valuation_does_not_flag_vix_derived_premium(monkeypatch):
    rates = {
        "risk_free_rate": 0.043,
        "market_risk_premium": 0.062,
        "field_sources": {"risk_free_rate": "FRED", "market_risk_premium": "derived_from_vix"},
    }
    vt, result, premium_warnings = _etf_with_rates(monkeypatch, rates)
    assert result["inputs"]["market_risk_premium"] == pytest.approx(0.062)
    assert result["inputs"]["market_risk_premium_source"] == "derived_from_vix"
    assert premium_warnings == []
    assert not any("not market data" in line for line in result["valuation_key_assumptions"])

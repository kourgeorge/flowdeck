"""get_indicators must turn a guessed indicator name into a usable correction.

Runs on 2026-10-14 sent indicator="sma"; the backend answered with a bare HTTP 500, so
the Technical Analyst never learned which names were valid.
"""

from ai_engine.tradingagents.agents.utils import technical_indicators_tools as tools


def test_unknown_indicator_is_rejected_with_the_valid_names(monkeypatch):
    def _no_backend(*_a, **_k):
        raise AssertionError("an invalid name must not reach the backend")

    monkeypatch.setattr(tools, "get_indicators_via_service", _no_backend)
    out = tools.get_indicators.invoke(
        {"symbol": "AAPL", "indicator": "sma", "curr_date": "2026-10-14", "look_back_days": 60}
    )
    assert "unsupported indicator 'sma'" in out
    assert all(name in out for name in tools.SUPPORTED_INDICATORS)


def test_supported_indicator_is_passed_through(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "require_info_service", lambda: None)
    monkeypatch.setattr(tools, "get_indicators_via_service", lambda *a: calls.append(a) or "data")
    out = tools.get_indicators.invoke(
        {"symbol": "AAPL", "indicator": "close_50_sma", "curr_date": "2026-10-14", "look_back_days": 60}
    )
    assert out == "data"
    assert calls == [("AAPL", "close_50_sma", "2026-10-14", 60)]

"""Analyst consensus groups Strong Buy with Buy (and Strong Sell with Sell),
and target_price is only ever the mean target."""

import pandas as pd

from data_layer.vendors import y_finance


def _fake_ticker(monkeypatch, counts, info):
    class FakeTicker:
        def __init__(self, *args, **kwargs):
            self.recommendations = pd.DataFrame([{"period": "0m", **counts}])
            self.info = info

    monkeypatch.setattr(y_finance.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(y_finance, "get_yf_session", lambda: None)


def _counts(strong_buy=0, buy=0, hold=0, sell=0, strong_sell=0):
    return {"strongBuy": strong_buy, "buy": buy, "hold": hold, "sell": sell, "strongSell": strong_sell}


def test_split_bullish_votes_beat_hold_and_missing_mean_leaves_target_empty(monkeypatch):
    # The gaps-bot repro: 12 + 15 bullish beats 16 hold; Yahoo's key says "buy".
    _fake_ticker(
        monkeypatch,
        _counts(strong_buy=12, buy=15, hold=16, sell=1),
        {"recommendationKey": "buy", "targetHighPrice": 300.0, "targetLowPrice": 150.0},
    )
    result = y_finance.get_analyst_recommendations("abc")
    assert result["recommendation"] == "BUY"
    assert result["target_price"] is None
    assert result["breakdown"] == {"Strong Buy": 12, "Buy": 15, "Hold": 16, "Sell": 1, "Strong Sell": 0}
    assert result["price_targets"]["high"] == 300.0
    assert result["price_targets"]["low"] == 150.0
    assert result["price_targets"]["average"] is None


def test_clear_hold_majority(monkeypatch):
    _fake_ticker(
        monkeypatch,
        _counts(strong_buy=2, buy=3, hold=20, sell=2, strong_sell=1),
        {"targetMeanPrice": 210.5},
    )
    result = y_finance.get_analyst_recommendations("abc")
    assert result["recommendation"] == "HOLD"
    assert result["target_price"] == 210.5


def test_tie_falls_back_to_recommendation_key(monkeypatch):
    _fake_ticker(monkeypatch, _counts(strong_buy=5, buy=5, hold=10), {"recommendationKey": "strong_sell"})
    assert y_finance.get_analyst_recommendations("abc")["recommendation"] == "SELL"


def test_tie_without_key_gives_no_recommendation(monkeypatch):
    _fake_ticker(monkeypatch, _counts(buy=4, sell=4), {})
    assert y_finance.get_analyst_recommendations("abc")["recommendation"] is None


def test_no_counts_uses_recommendation_key(monkeypatch):
    _fake_ticker(monkeypatch, _counts(), {"recommendationKey": "hold"})
    assert y_finance.get_analyst_recommendations("abc")["recommendation"] == "HOLD"

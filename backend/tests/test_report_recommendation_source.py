"""The recommendation, confidence and views come from investment_plan first.

Since the Research/Risk merge only investment_plan carries them and final_trade_decision
is no longer written, but the watchlist report still read final_trade_decision and then
the trader, so a current run's BUY 0.8 came out as recommendation/confidence/views None.
"""

from ai_engine.report_meta import pick_recommendation_meta
from ai_engine.watchlist_consulting.report_payload import build_payload


class _ReportService:
    def __init__(self, scores):
        self._scores = scores

    def get_latest_execution_for_ticker(self, ticker):
        return ("run-1", "2026-11-01")

    def get_reports_with_scores(self, execution_id, execution_type="ticker"):
        return self._scores


class _Fetcher:
    def get_quote(self, ticker):
        return None

    def get_company_info(self, ticker):
        return None


def _entry(scores):
    payload = build_payload(
        {"id": 1, "email": "a@b.c", "name": "A"},
        ["AAPL"],
        report_service=_ReportService(scores),
        quote_fetcher=_Fetcher(),
    )
    return payload["entries"][0]


def test_current_run_with_only_investment_plan_gives_buy_with_views():
    entry = _entry({
        "investment_plan": {
            "recommendation": "BUY",
            "confidence": 0.8,
            "score": 4,
            "score_label": "Conviction Score",
            "bull_viewpoint": "bull case",
            "bear_viewpoint": "bear case",
            "neutral_viewpoint": "neutral case",
        },
        # Trader output failed: no recommendation.
        "trader_investment_plan": {"score": 2, "score_label": "x"},
    })
    assert entry["recommendation"] == "BUY"
    assert entry["confidence"] == 0.8
    assert entry["score"] == 4
    assert entry["bull_viewpoint"] == "bull case"
    assert entry["bear_viewpoint"] == "bear case"
    assert entry["neutral_viewpoint"] == "neutral case"


def test_old_run_prefers_investment_plan_over_final_trade_decision():
    scores = {
        "final_trade_decision": {
            "recommendation": "SELL",
            "confidence": 0.3,
            "bull_viewpoint": "old bull",
        },
        "investment_plan": {
            "recommendation": "HOLD",
            "confidence": 0.6,
            "bull_viewpoint": "rm bull",
        },
        "trader_investment_plan": {"recommendation": "BUY", "confidence": 0.9},
    }
    key, meta = pick_recommendation_meta(scores)
    assert key == "investment_plan"
    assert meta["recommendation"] == "HOLD"
    entry = _entry(scores)
    assert entry["recommendation"] == "HOLD"
    assert entry["confidence"] == 0.6
    assert entry["bull_viewpoint"] == "rm bull"


def test_falls_back_to_final_trade_decision_then_trader():
    assert pick_recommendation_meta({
        "investment_plan": {"recommendation": None, "confidence": 0.5},
        "final_trade_decision": {"recommendation": "SELL"},
        "trader_investment_plan": {"recommendation": "BUY"},
    })[0] == "final_trade_decision"
    assert pick_recommendation_meta({
        "investment_plan": {"confidence": 0.5},
        "trader_investment_plan": {"recommendation": "BUY"},
    })[0] == "trader_investment_plan"


def test_no_recommendation_anywhere_gives_none():
    scores = {
        "investment_plan": {"confidence": 0.5, "bull_viewpoint": "x"},
        "final_trade_decision": {"score": 3},
        "trader_investment_plan": {},
    }
    assert pick_recommendation_meta(scores) == (None, {})
    assert pick_recommendation_meta(None) == (None, {})
    entry = _entry(scores)
    assert entry["recommendation"] is None
    assert entry["confidence"] is None
    assert entry["bull_viewpoint"] is None

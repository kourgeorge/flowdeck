"""The standalone runner must save the event-monitor baseline on trader_investment_plan.

It used to carry its own copy of the report helpers that never gained the event signal,
so after a manual standalone run the event monitor returned skipped_no_baseline for that
ticker and stopped re-checking it.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_layer
import database
import processing
import run_analysis_standalone as standalone
from services import token_service


_DEFAULT_CHUNKS = [
    {"investment_plan": "Plan", "recommendation": "BUY", "recommendation_score": 4},
    {
        "trader_investment_plan": "Trader plan",
        "trader_recommendation": "BUY",
        "trader_key_takeaways": ["Buy the dip"],
    },
]


def _run_standalone(monkeypatch, tmp_path, *, event_summary, chunks=None, notified=None):
    saved = {}
    chunks = _DEFAULT_CHUNKS if chunks is None else chunks
    notified = [] if notified is None else notified
    gateway = SimpleNamespace(get_quote=lambda _ticker: {"current_price": 101.5, "currency": "usd"})
    event_calls = []

    def fake_event_summary(gw, ticker, as_of_date=None):
        event_calls.append((gw, ticker, as_of_date))
        if isinstance(event_summary, Exception):
            raise event_summary
        return event_summary

    class FakeGraph:
        def __init__(self, *, config, **kwargs):
            self.config = config
            self.propagator = SimpleNamespace(
                create_initial_state=lambda ticker, date: {"ticker": ticker},
                get_graph_args=lambda **kw: {},
            )
            self.graph = SimpleNamespace(stream=lambda state, **kw: iter(chunks))

    class FakeSession:
        def close(self):
            pass

    monkeypatch.setattr(sys, "argv", [
        "run_analysis_standalone.py", "--ticker", "xyz", "--analysis-date", "2026-11-02",
        "--info-service-url", "http://127.0.0.1:1", "--analysts", "market",
        "--results-dir", str(tmp_path),
    ])
    monkeypatch.setattr(standalone, "init_db", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", FakeSession)
    monkeypatch.setattr(token_service, "get_system_user_id", lambda db: 1)
    monkeypatch.setattr(token_service, "record_analysis_run", lambda uid, ticker, db: 4242)
    monkeypatch.setattr(standalone, "get_config_from_env", lambda overrides: {})
    monkeypatch.setattr(standalone, "TradingAgentsGraph", FakeGraph)
    monkeypatch.setattr(standalone, "notify_subscribers_new_report", lambda **kw: notified.append(kw))
    monkeypatch.setattr(standalone, "save_report", lambda run_id, key, content, metadata: saved.__setitem__(key, (run_id, content, metadata)))
    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: gateway)
    monkeypatch.setattr(processing, "get_ticker_event_summary", fake_event_summary)

    standalone.main()
    return saved, event_calls, gateway


def test_standalone_trader_plan_stores_event_baseline(monkeypatch, tmp_path):
    summary = SimpleNamespace(event_score=7.25, dominant_events=["gap_up", "volume_spike"])
    saved, event_calls, gateway = _run_standalone(monkeypatch, tmp_path, event_summary=summary)

    run_id, content, meta = saved["trader_investment_plan"]
    assert run_id == 4242
    assert content == "Trader plan"
    assert meta["event_score"] == 7.25
    assert meta["dominant_events"] == ["gap_up", "volume_spike"]
    assert meta["key_takeaways"] == ["Buy the dip"]
    assert meta["recommendation"] == "BUY"
    # The signal is taken as of the analysis date, not today, so a backdated run
    # does not leak later price action into its baseline.
    assert event_calls == [(gateway, "XYZ", "2026-11-02")]


def test_standalone_omits_event_baseline_when_signal_unavailable(monkeypatch, tmp_path):
    saved, _, _ = _run_standalone(monkeypatch, tmp_path, event_summary=RuntimeError("no bars"))

    meta = saved["trader_investment_plan"][2]
    # Honest emptiness: no made-up 0.0 baseline when the signal could not be read.
    assert "event_score" not in meta
    assert "dominant_events" not in meta


def test_standalone_investment_plan_metadata_is_flat(monkeypatch, tmp_path):
    chunks = [
        {
            "investment_plan": "Plan",
            "recommendation": "SELL",
            "recommendation_score": 2,
            "bull_summary": ["bull point"],
            "report_usage": {"investment_plan": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cost_usd": 0.01}},
        },
    ]
    saved, _, _ = _run_standalone(monkeypatch, tmp_path, event_summary=RuntimeError("n/a"), chunks=chunks)

    meta = saved["investment_plan"][2]
    # Same shape analysis_service saves: fields at the top level, not under metadata.metadata.
    assert "metadata" not in meta
    assert meta["recommendation"] == "SELL"
    assert meta["score"] == 2
    assert meta["confidence"] == 0.4
    assert meta["score_label"] == "Conviction Score"
    assert meta["current_price"] == 101.5
    assert meta["total_tokens"] == 15
    assert meta["bull_viewpoint"] == ["bull point"]
    assert "resources" in meta and "agent_steps" in meta


def test_standalone_email_sent_with_plan_recommendation(monkeypatch, tmp_path):
    notified = []
    _run_standalone(monkeypatch, tmp_path, event_summary=RuntimeError("n/a"), notified=notified)

    assert len(notified) == 1
    assert notified[0]["recommendation"] == "BUY"
    assert notified[0]["confidence"] == 0.8


def test_standalone_email_without_investment_plan(monkeypatch, tmp_path):
    notified = []
    chunks = [{"trader_investment_plan": "Trader plan", "trader_recommendation": "HOLD"}]
    saved, _, _ = _run_standalone(monkeypatch, tmp_path, event_summary=RuntimeError("n/a"), chunks=chunks, notified=notified)

    assert "investment_plan" not in saved
    assert "trader_investment_plan" in saved
    # No plan means no Research Manager recommendation: send without one, never a made-up value.
    assert len(notified) == 1
    assert notified[0]["recommendation"] is None
    assert notified[0]["confidence"] is None

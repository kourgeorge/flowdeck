"""When the Research Manager's structured call fails, no recommendation is invented.

It falls back to a plain-text plan with recommendation=None. analysis_service used to
default that to "HOLD", save it in the investment_plan metadata and email it, so readers
saw a HOLD the model never gave. The same HOLD default lived in
resolve_trade_signal_from_state, which TradingAgentsGraph.propagate() returns.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine.tradingagents.agents.managers import research_manager as rm_module
from ai_engine.tradingagents.agents.managers.research_manager import create_research_manager
from ai_engine.tradingagents.graph.signal_processing import resolve_trade_signal_from_state
from services import analysis_service

from tests.test_analysis_capacity import COMPLETE_REPORTS, runtime  # noqa: F401 (fixture)


class _FakeLLM:
    """Structured call raises; the plain-text fallback returns a narrative plan."""

    def invoke(self, prompt, **kwargs):
        return SimpleNamespace(content="Plain-text plan", response_metadata={}, usage_metadata=None)


class _FakeMemory:
    def get_memories(self, situation, n_matches=2):
        return []


def _state():
    return {
        "market_report": "m",
        "sentiment_report": "s",
        "fundamentals_report": "f",
        "investment_debate_state": {"history": "debate", "count": 1},
    }


def test_research_manager_fallback_leaves_recommendation_empty(monkeypatch):
    def failing_structured_output(llm, schema):
        raise ValueError("json_schema ignored by provider")

    monkeypatch.setattr(rm_module, "structured_output", failing_structured_output)
    out = create_research_manager(_FakeLLM(), _FakeMemory())(_state())

    assert out["investment_plan"] == "Plain-text plan"
    assert out["recommendation"] is None
    assert out["recommendation_score"] is None
    step = out["report_steps_by_report"]["investment_plan"][0]
    assert step["status"] == "fallback"


def test_resolve_trade_signal_returns_none_without_a_signal():
    assert resolve_trade_signal_from_state({"recommendation": None, "trader_recommendation": None}) is None
    assert resolve_trade_signal_from_state({}) is None
    assert resolve_trade_signal_from_state({"recommendation": None, "trader_recommendation": "sell"}) == "SELL"


def test_analysis_service_saves_and_emails_no_recommendation_on_fallback(runtime, monkeypatch):  # noqa: F811
    rt = runtime
    saved = {}
    real_save = analysis_service.save_report

    def capture(run_id, key, content=None, metadata=None, **kw):
        saved[key] = metadata
        return real_save(run_id, key, content=content, metadata=metadata, **kw)

    monkeypatch.setattr(analysis_service, "save_report", capture)
    rt.streams["FALLBACK"] = lambda: iter([
        {"investment_plan": "Plain-text plan", "recommendation": None, "recommendation_score": None},
        dict(COMPLETE_REPORTS),
    ])
    run_id = rt.start("FALLBACK")
    rt.executor.shutdown(wait=True)

    assert rt.execution(run_id)[0] == "completed"
    meta = saved["investment_plan"]
    assert meta.get("recommendation") is None
    assert meta["recommendation_missing_reason"] == "structured_output_failed"
    rt.notify.assert_called_once()
    assert rt.notify.call_args.kwargs["recommendation"] is None

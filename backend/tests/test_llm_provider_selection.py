"""System-started runs must use the same provider as user-started ones.

Event-monitor re-runs and the major-ticker sync used to hardcode "azure", so a server
configured with LLM_PROVIDER set to another provider ran user analyses fine while every
system@flowdeck.internal run failed on missing AZURE_OPENAI_* credentials.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sync_major_stocks
from ai_engine.llm_provider import configured_provider
from services import event_monitor_service as ems


class _RecordingAnalysisService:
    def __init__(self):
        self.calls = []

    def start_analysis(self, **kwargs):
        self.calls.append(kwargs)
        return (kwargs.get("analysis_run_id"), False)


def test_configured_provider_reads_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "  OpenAI\n")
    assert configured_provider() == "openai"


def test_configured_provider_defaults_to_azure_when_unset_or_blank(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert configured_provider() == "azure"
    monkeypatch.setenv("LLM_PROVIDER", "   ")
    assert configured_provider() == "azure"


def test_event_monitor_rerun_uses_configured_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "cerebras")
    monkeypatch.setattr(ems.token_service, "record_analysis_run", lambda *a, **k: 42)
    service = _RecordingAnalysisService()

    ems._start_rerun(None, "AMZN", creator_id=1, analysis_date="2026-10-13", analysis_service=service)

    assert service.calls[0]["llm_provider"] == "cerebras"


def test_major_ticker_sync_uses_configured_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setattr(sync_major_stocks.token_service, "record_analysis_run", lambda *a, **k: 42)
    service = _RecordingAnalysisService()

    sync_major_stocks.run_analyses_for_tickers(
        ["BMNR"], "2026-10-13", service, db=None, creator_id=1, wait_for_completion=False
    )

    assert service.calls[0]["llm_provider"] == "openai"

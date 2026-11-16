"""The brief agent must not import backend services (backend -> ai_engine only).

context_builder used to import services.info_fetcher, services.report_service and
services.share_service. Now the backend passes the fetcher and a platform-reports
loader in through run_digest.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_engine.briefing_agent import context_builder

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIEFING_DIR = REPO_ROOT / "ai_engine" / "briefing_agent"
_SERVICES_IMPORT = re.compile(r"^\s*(from\s+services[\s.]|import\s+services\b)", re.M)


def test_briefing_agent_has_no_services_import():
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in BRIEFING_DIR.rglob("*.py")
        if _SERVICES_IMPORT.search(path.read_text())
    ]
    assert offenders == []


class _Fetcher:
    def get_daily_market_movers(self, limit):
        return {"gainers": [{"symbol": "AAA", "regularMarketChangePercent": 5.0}], "losers": []}

    def get_company_info_batch(self, tickers):
        return {}


def _build(monkeypatch, loader):
    monkeypatch.setattr(context_builder, "_load_portfolio_tickers", lambda *_: [])
    monkeypatch.setattr(context_builder, "_get_user_context_snapshot", lambda *_: None)
    monkeypatch.setattr(context_builder, "_fetch_global_news", lambda *a, **k: None)
    monkeypatch.setattr(context_builder, "_fetch_web_snippet", lambda *a, **k: None)
    monkeypatch.setattr(context_builder, "_fetch_polymarket_markets", lambda *_: {})
    return context_builder.build_digest_context(
        user_id=1,
        digest_date="2026-11-16",
        max_priority_tickers=3,
        db=None,
        fetcher=_Fetcher(),
        platform_reports_loader=loader,
    )


def test_injected_loader_fills_reports_and_share_urls(monkeypatch):
    ctx = _build(monkeypatch, lambda t: ({"market": {"content": t}}, f"https://x/r/{t}"))
    assert ctx.platform_reports == {"AAA": {"market": {"content": "AAA"}}}
    assert ctx.share_urls == {"AAA": "https://x/r/AAA"}


def test_loader_failure_leaves_ticker_empty(monkeypatch):
    def _boom(_t):
        raise RuntimeError("db down")

    ctx = _build(monkeypatch, _boom)
    assert ctx.platform_reports == {"AAA": {}}
    assert ctx.share_urls == {}


def test_missing_fetcher_is_refused():
    with pytest.raises(ValueError):
        context_builder.build_digest_context(user_id=1, digest_date="2026-11-16", max_priority_tickers=3, db=None)


def test_missing_portfolio_tickers_loader_is_refused(monkeypatch):
    # Falling back to market movers would look like a real brief for a user with no tickers.
    monkeypatch.setattr(context_builder, "_fetch_global_news", lambda *a, **k: None)
    monkeypatch.setattr(context_builder, "_fetch_web_snippet", lambda *a, **k: None)
    with pytest.raises(ValueError, match="portfolio_tickers_loader"):
        context_builder.build_digest_context(
            user_id=1, digest_date="2026-11-16", max_priority_tickers=3, db=None, fetcher=_Fetcher()
        )
    assert context_builder._load_portfolio_tickers(1, "db", lambda uid, db: [f"{uid}{db}"]) == ["1db"]


def test_digest_service_loader_matches_old_behaviour(monkeypatch):
    from services import digest_service, report_service, share_service

    class _Svc:
        def get_latest_execution_for_ticker(self, ticker):
            return (11, "2026-11-15") if ticker == "AAA" else None

        def get_reports_with_scores(self, execution_id, *, execution_type):
            return {"market": {"execution_id": execution_id, "type": execution_type}}

    monkeypatch.setattr(report_service, "ReportService", _Svc)
    monkeypatch.setattr(share_service, "get_share_url", lambda eid: f"https://x/r/{eid}")

    assert digest_service.load_platform_reports_for_ticker("AAA") == (
        {"market": {"execution_id": 11, "type": "ticker"}},
        "https://x/r/11",
    )
    assert digest_service.load_platform_reports_for_ticker("BBB") == ({}, None)


def test_run_and_store_digest_injects_dependencies(monkeypatch):
    import asyncio

    import ai_engine.briefing_agent as briefing_agent
    from services import digest_service, info_fetcher, report_service, token_service

    seen: dict = {}
    sentinel = object()

    def _fake_run_digest(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(narrative="n", what_to_watch="w", priority_tickers=[])

    monkeypatch.setattr(token_service, "deduct_for_digest", lambda *a: (True, 5))
    monkeypatch.setattr(briefing_agent, "run_digest", _fake_run_digest)
    monkeypatch.setattr(info_fetcher, "get_info_fetcher", lambda: sentinel)
    monkeypatch.setattr(report_service, "save_report", lambda *a, **k: None)
    monkeypatch.setattr(report_service, "update_execution_status", lambda *a, **k: None)

    try:
        asyncio.run(
            digest_service.run_and_store_digest(None, 7, digest_date="2026-11-16", span_type="daily")
        )
    except Exception:
        pass  # only the run_digest call matters here
    assert seen["fetcher"] is sentinel
    assert seen["platform_reports_loader"] is digest_service.load_platform_reports_for_ticker
    assert seen["portfolio_tickers_loader"] is digest_service.load_portfolio_tickers
    assert seen["recent_digests_loader"] is digest_service.load_recent_digest_rows


def _full_result():
    # Every optional field set, so a missing metadata key in either path shows up.
    return SimpleNamespace(
        narrative="n",
        what_to_watch="w",
        digest_date="2026-11-16",
        span_type="daily",
        span_label="Daily",
        priority_tickers=["AAA"],
        important_events=[{"title": "e"}],
        focus_snapshot={"AAA": {"price": 1.0}},
        references=[{"url": "u"}],
        resources=["r"],
        agent_steps=[{"step": 1}],
        input_tokens=1,
        output_tokens=2,
        total_tokens=3,
        cost_usd=0.01,
        models_used=["m"],
    )


def _patch_persistence(monkeypatch, saved, statuses):
    from services import report_service

    monkeypatch.setattr(
        report_service, "save_report", lambda eid, rtype, content="", metadata=None: saved.append((eid, metadata))
    )
    monkeypatch.setattr(
        report_service, "update_execution_status", lambda eid, status, **k: statuses.append((eid, status))
    )


def test_standalone_script_marks_completed_with_same_metadata(monkeypatch):
    import asyncio
    import importlib

    import ai_engine.briefing_agent as briefing_agent
    import data_layer
    import database
    import dotenv
    from data_layer import market
    from services import digest_service, edgar_service, info_fetcher, report_service, token_service

    # Keep backend/.env and real services out of the test process.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(database, "init_db", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(data_layer, "init_data_gateway", lambda **k: None)
    monkeypatch.setattr(market, "MarketDataLayer", lambda: None)
    monkeypatch.setattr(edgar_service, "get_edgar_service", lambda: None)
    monkeypatch.setattr(report_service, "ReportService", lambda: None)
    monkeypatch.setattr(info_fetcher, "get_info_fetcher", lambda: object())
    monkeypatch.setattr(briefing_agent, "run_digest", lambda **k: _full_result())
    monkeypatch.setattr(token_service, "record_execution", lambda **k: 41)
    monkeypatch.setattr(token_service, "deduct_for_digest", lambda *a: (True, 42))
    monkeypatch.setattr(token_service, "update_usage_with_llm_data", lambda **k: None)

    saved: list = []
    statuses: list = []
    _patch_persistence(monkeypatch, saved, statuses)

    script = importlib.import_module("run_briefing_standalone")
    monkeypatch.setattr(sys, "argv", ["run_briefing_standalone.py", "--user-id", "7", "--date", "2026-11-16"])
    script.main()

    asyncio.run(digest_service.run_and_store_digest(None, 7, digest_date="2026-11-16", span_type="daily"))

    assert statuses == [(41, "completed"), (42, "completed")]
    (script_eid, script_meta), (api_eid, api_meta) = saved
    assert (script_eid, api_eid) == (41, 42)
    assert script_meta == api_meta
    for key in ("important_events", "span_type", "span_label", "focus_snapshot", "total_tokens"):
        assert key in script_meta

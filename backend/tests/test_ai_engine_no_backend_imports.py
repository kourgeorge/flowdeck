"""ai_engine must not import backend code (backend -> ai_engine only).

T-52 removed the brief's services imports; T-63 removed the rest (stocks_discovery,
chat user_context, watchlist_consulting, portfolio_deep_research). The data now comes
in from the backend caller or, for the separately-run portfolio research, over HTTP.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_ENGINE = REPO_ROOT / "ai_engine"
WATCHLIST_DIR = AI_ENGINE / "watchlist_consulting"

# backend.processing (the event layer) is still imported by the brief and stocks
# discovery, and the brief's history loader still reads backend.models. Moving them
# needs files outside ai_engine/backend/services, so they are listed here until then.
_PENDING = {
    "ai_engine/briefing_agent/agents.py": {"backend.processing"},
    "ai_engine/briefing_agent/context_builder.py": {"backend.processing"},
    "ai_engine/briefing_agent/state.py": {"backend.processing"},
    "ai_engine/briefing_agent/runner.py": {"backend", "backend.processing", "backend.models.db_models"},
    "ai_engine/stocks_discovery/runner.py": {"backend.processing"},
    "ai_engine/stocks_discovery/deterministic.py": {"backend.processing"},
}


def _imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def _is_backend(module: str) -> bool:
    top = module.split(".")[0]
    return top in ("services", "backend")


def test_ai_engine_has_no_services_or_backend_import():
    offenders = []
    for path in AI_ENGINE.rglob("*.py"):
        rel = str(path.relative_to(REPO_ROOT))
        allowed = _PENDING.get(rel, set())
        for module in _imported_modules(ast.parse(path.read_text())):
            if _is_backend(module) and module not in allowed:
                offenders.append(f"{rel}: {module}")
    assert offenders == []


def test_no_file_imports_services_at_all():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {m}"
        for path in AI_ENGINE.rglob("*.py")
        for m in _imported_modules(ast.parse(path.read_text()))
        if m.split(".")[0] == "services" or m.startswith("backend.services")
    ]
    assert offenders == []


# --- portfolio_deep_research: separate process, uses the public HTTP endpoints ---


def test_risk_profiler_reads_sector_and_beta_over_http(monkeypatch):
    from ai_engine.portfolio_deep_research import portfolio_risk_profiler as prp
    from ai_engine.tradingagents.datasources import info_service_client

    calls = []

    def fake_get(session, base_url, path, params=None, timeout=60):
        calls.append(path)
        return {"sector": "Technology"} if "/company/" in path else {"beta": 1.5}

    monkeypatch.setenv("INFO_SERVICE_URL", "http://info")
    monkeypatch.setattr(info_service_client, "_get", fake_get)

    assert prp.calculate_sector_exposure(["aaa"], {}) == {"Technology": 100.0}
    assert prp.calculate_beta_analysis(["aaa"], {})["portfolio_beta"] == 1.5
    assert calls == ["/api/data/company/AAA", "/api/data/extended-info/AAA"]


def test_risk_profiler_http_failure_gives_empty(monkeypatch):
    from ai_engine.portfolio_deep_research import portfolio_risk_profiler as prp
    from ai_engine.tradingagents.datasources import info_service_client

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setenv("INFO_SERVICE_URL", "http://info")
    monkeypatch.setattr(info_service_client, "_get", boom)
    assert prp._fetch_company_info_from_service("AAA") == {}
    assert prp._fetch_extended_info_from_service("AAA") == {}


# --- stocks_discovery: in the backend process, fetcher + loader injected ---


def test_stocks_discovery_refuses_without_fetcher():
    from ai_engine.stocks_discovery import run_stocks_discovery

    with pytest.raises(ValueError):
        run_stocks_discovery(1, "2026-11-16", None)


def test_stocks_discovery_passes_platform_reports_loader(monkeypatch):
    from ai_engine.stocks_discovery import runner

    seen: dict = {}

    class _Stop(Exception):
        pass

    def fake_build(**kwargs):
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(runner, "build_digest_context", fake_build)
    loader = lambda t: ({}, None)  # noqa: E731
    fetcher = object()
    with pytest.raises(_Stop):
        runner.run_stocks_discovery(1, "2026-11-16", None, fetcher=fetcher, platform_reports_loader=loader)
    assert seen["fetcher"] is fetcher
    assert seen["platform_reports_loader"] is loader


def test_backend_stocks_discovery_entry_injects_dependencies(monkeypatch):
    import ai_engine.stocks_discovery as sd
    from services import digest_service, info_fetcher

    seen: dict = {}
    sentinel = object()
    monkeypatch.setattr(info_fetcher, "get_info_fetcher", lambda: sentinel)
    monkeypatch.setattr(sd, "run_stocks_discovery", lambda *a, **k: seen.update(k) or "ok")

    assert digest_service.run_stocks_discovery_for_user(1, "2026-11-16", None) == "ok"
    assert seen["fetcher"] is sentinel
    assert seen["platform_reports_loader"] is digest_service.load_platform_reports_for_ticker


# --- chat user_context: in the backend process, uses the startup data gateway ---


def test_user_context_uses_gateway_and_has_no_services_fallback(monkeypatch):
    import data_layer
    from ai_engine.agent.tools import user_context

    gw = SimpleNamespace(get_user_context=lambda uid, db: f"ctx-{uid}")
    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: gw)
    assert user_context._get_user_context(5, None) == "ctx-5"

    def missing():
        raise RuntimeError("Data gateway not initialized")

    monkeypatch.setattr(data_layer, "get_data_gateway", missing)
    with pytest.raises(RuntimeError):
        user_context._get_user_context(5, None)


# --- watchlist_consulting: backend entry passes payload loader and fetcher ---


@pytest.fixture
def watchlist_path(monkeypatch):
    monkeypatch.syspath_prepend(str(WATCHLIST_DIR))


class _Fetcher:
    def get_company_info(self, t):
        return {"name": f"{t} Inc", "sector": "Tech", "industry": "Chips"}

    def get_quote(self, t):
        return {"current_price": 10.0, "daily_change": 1.0, "daily_change_percent": 11.1}

    def get_historical(self, t, period, interval):
        return {"ticker": t, "data": [{"close": 10.0}, {"close": 11.0}, {"close": 10.0}]}

    def get_financial_charts(self, t, freq):
        return {"ticker": t, "series": []}


class _Reports:
    def get_latest_execution_for_ticker(self, t):
        return (3, "2026-11-15") if t == "AAA" else None

    def get_reports_with_scores(self, eid, execution_type):
        return {
            "final_trade_decision": {"recommendation": "BUY", "confidence": 0.7, "score": 8, "score_label": "Good"},
            "investment_plan": {"expected_return_pct": 5.0},
        }


def test_build_payload_uses_injected_services():
    from ai_engine.watchlist_consulting.report_payload import build_payload

    user = {"id": 1, "email": "a@b.c", "name": "A"}
    out = build_payload(user, ["AAA", "BBB"], report_service=_Reports(), quote_fetcher=_Fetcher())
    a, b = out["entries"]
    assert out["user"] == user and out["tickers"] == ["AAA", "BBB"]
    assert a["name"] == "AAA Inc" and a["recommendation"] == "BUY" and a["confidence"] == 0.7
    assert a["score"] == 8 and a["expected_return_pct"] == 5.0 and a["report_date"] == "2026-11-15"
    assert a["quote"] == {"current_price": 10.0, "daily_change": 1.0, "daily_change_percent": 11.1}
    assert b["recommendation"] is None and b["report_date"] is None
    assert build_payload(None, [], report_service=None, quote_fetcher=None)["error"] == "User not found"
    assert build_payload(user, [], report_service=None, quote_fetcher=None) == {"user": user, "tickers": [], "entries": []}


def test_watchlist_stages_use_injected_fetcher(watchlist_path):
    import stage3_theme_miner
    import stage6_data_builder
    from pipeline_schemas import DataJob

    snap = stage3_theme_miner._build_exposure_snapshot(["AAA", "BBB"], _Fetcher())
    assert snap.sector_counts == {"Tech": 2} and snap.industry_counts == {"Chips": 2}
    assert stage3_theme_miner._build_exposure_snapshot(["AAA"], None).sector_counts == {}

    job = DataJob.model_construct(tickers=["AAA"])
    by_ticker, _notes = stage6_data_builder._run_data_jobs([job], {}, _Fetcher())
    assert by_ticker["AAA"]["sector"] == "Tech"
    assert by_ticker["AAA"]["historical"]["data"][1]["close"] == 11.0
    assert "volatility_pct" in by_ticker["AAA"]
    assert stage6_data_builder._run_data_jobs([job], {}, None) == ({}, [])


def test_conductor_refuses_without_backend_dependencies(watchlist_path):
    import conductor

    with pytest.raises(ValueError):
        conductor.run_pipeline(email="a@b.c")


def test_backend_watchlist_entry_injects_dependencies(monkeypatch, watchlist_path):
    import conductor
    from services import info_fetcher, watchlist_report_service

    sentinel = _Fetcher()
    seen: dict = {}
    monkeypatch.setattr(info_fetcher, "get_info_fetcher", lambda: sentinel)
    monkeypatch.setattr(conductor, "run_pipeline", lambda **kw: seen.update(kw) or {"ok": True})
    monkeypatch.setattr(
        watchlist_report_service, "load_watchlist_payload", lambda **kw: {"loaded": kw}
    )

    assert watchlist_report_service.run_watchlist_pipeline(email="a@b.c") == {"ok": True}
    assert seen["fetcher"] is sentinel and seen["email"] == "a@b.c"
    assert seen["payload_loader"](user_id=None, email="a@b.c") == {
        "loaded": {"user_id": None, "email": "a@b.c", "fetcher": sentinel}
    }

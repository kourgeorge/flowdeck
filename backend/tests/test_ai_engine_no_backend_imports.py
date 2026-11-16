"""ai_engine must not import backend code (backend -> ai_engine only).

T-52 removed the brief's services imports; T-63 removed the rest (stocks_discovery,
chat user_context, watchlist_consulting, portfolio_deep_research). The data now comes
in from the backend caller or, for the separately-run portfolio research, over HTTP.
T-74 moved the event layer to ai_engine.processing and dropped the brief's
backend.models import. T-87 removed the models.db_models imports (the brief's recent
briefs and subscriptions, the chat's subscription/memory tools): the backend now passes
those lookups in. The guard used to check only "services" and "backend", which missed
"models" because backend/ is on sys.path; it now checks every backend top-level package.
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


def _imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


# backend/'s top-level packages. backend/ is on sys.path in the app and the tests, so
# "models.db_models" is backend code even though it does not say "backend".
_BACKEND_PACKAGES = ("services", "backend", "models", "database", "routers", "config", "auth", "data_layer")

# The only allowed exceptions: chat tools that read the data gateway the backend sets up
# at startup (init_data_gateway in backend/main.py). Each one catches ImportError and
# RuntimeError and falls back to the public HTTP API (or reports an error), so ai_engine
# still works without the backend. Each is covered by a test below.
_ALLOWED = {
    ("ai_engine/agent/tools/user_context.py", "data_layer"),  # get_user_context
    ("ai_engine/agent/tools/platform_reports.py", "data_layer"),  # reports and report dates
    ("ai_engine/agent/tools/events.py", "data_layer"),  # event summary
}


def _is_backend(module: str) -> bool:
    return module.split(".")[0] in _BACKEND_PACKAGES


def _backend_imports():
    for path in AI_ENGINE.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for module in _imported_modules(ast.parse(path.read_text())):
            if _is_backend(module):
                yield rel, module


def test_ai_engine_has_no_backend_import():
    offenders = [f"{rel}: {m}" for rel, m in _backend_imports() if (rel, m) not in _ALLOWED]
    assert offenders == []


def test_allowlist_has_no_stale_entries():
    # An entry that no longer matches an import should be removed, not kept "just in case".
    assert _ALLOWED <= set(_backend_imports())


def test_guard_flags_models_db_models():
    tree = ast.parse("from models.db_models import Subscription\nimport database\nimport config.x")
    assert [m for m in _imported_modules(tree) if _is_backend(m)] == ["models.db_models", "database", "config.x"]


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
    tickers_loader = lambda uid, db: []  # noqa: E731
    fetcher = object()
    with pytest.raises(_Stop):
        runner.run_stocks_discovery(
            1, "2026-11-16", None, fetcher=fetcher, platform_reports_loader=loader,
            portfolio_tickers_loader=tickers_loader,
        )
    assert seen["fetcher"] is fetcher
    assert seen["platform_reports_loader"] is loader
    assert seen["portfolio_tickers_loader"] is tickers_loader


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
    assert seen["portfolio_tickers_loader"] is digest_service.load_portfolio_tickers


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


def test_platform_report_dates_read_the_gateway(monkeypatch):
    import data_layer
    from ai_engine.agent.tools import platform_reports

    gw = SimpleNamespace(list_report_dates=lambda t: ["2026-11-15"] if t == "AAA" else [])
    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: gw)
    assert "`2026-11-15`" in platform_reports._fetch_historical_dates("aaa")


def test_events_tool_reads_the_gateway(monkeypatch):
    import data_layer
    import processing
    from ai_engine.agent.tools import events

    gw = object()
    seen = {}

    def fake_summary(gateway, ticker, as_of_date):
        seen["gateway"], seen["ticker"] = gateway, ticker
        return SimpleNamespace(model_dump=lambda mode: {"event_score": 1.0, "event_count": 0, "events": []})

    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: gw)
    monkeypatch.setattr(processing, "get_ticker_event_summary", fake_summary)
    assert "AAA" in events._fetch_events("aaa")
    assert seen == {"gateway": gw, "ticker": "AAA"}


class _Sub(SimpleNamespace):
    pass


class _Store:
    def __init__(self):
        self.profile = SimpleNamespace(ai_memory_text=None)

    def subscriptions_newest_first(self, uid, db):
        return [_Sub(ticker="BBB", created_at=None, email_updates=True)] if uid == 1 else []

    def subscriptions_by_ticker(self, uid, db):
        return [_Sub(ticker="AAA")] if uid == 1 else []

    def get_or_create_profile(self, uid, db):
        return self.profile


class _Db:
    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_user_tools_use_the_injected_store(monkeypatch):
    import data_layer
    from ai_engine.agent.tool import ExecutionContext
    from ai_engine.agent.tools import user_context

    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: object())
    store = _Store()
    subs = user_context.UserSubscriptionsTool(user_store=store)
    overview = user_context.PortfolioOverviewTool(user_store=store)
    memory = user_context.UpdateUserMemoryTool(user_store=store)
    ctx = ExecutionContext(user_id=1, db=_Db())
    assert "**BBB** — subscribed Unknown (email updates on)" in subs.execute(ctx).data
    assert subs.execute(ExecutionContext(user_id=2, db=_Db())).data.startswith("You have no subscribed stocks yet")
    assert overview.execute(ExecutionContext(user_id=2, db=_Db())).data.startswith("You have no subscribed stocks.")
    assert memory.execute(ctx, memory_note="likes AAA").ok
    assert store.profile.ai_memory_text.endswith("] likes AAA")


def test_user_tools_without_store_report_an_error():
    from ai_engine.agent.tool import ExecutionContext
    from ai_engine.agent.tools import user_context

    ctx = ExecutionContext(user_id=1, db=_Db())
    for tool in (user_context.UserSubscriptionsTool(), user_context.PortfolioOverviewTool()):
        assert tool.execute(ctx).error["code"] == "TOOL_ERROR"
    assert user_context.UpdateUserMemoryTool().execute(ctx, memory_note="x").error["code"] == "TOOL_ERROR"


def test_chat_service_hands_its_store_to_every_user_tool_path(monkeypatch):
    from ai_engine.agent import graph
    from ai_engine.agent.lc_tools import get_all_lc_tools
    from services import chat_service

    svc = chat_service.ChatService()
    monkeypatch.setattr(svc, "_get_llm", lambda: None)
    agent = svc._get_agent()
    assert isinstance(agent.user_store, chat_service.ChatUserStore)
    config = agent._make_config([], 1, object(), "", 3)
    assert config["configurable"]["user_store"] is agent.user_store
    # The lc tool wrappers close over the store; the store is per-process, not per-user.
    names = [t.name for t in get_all_lc_tools(user_id=1, db=object(), user_store=agent.user_store)]
    assert "get_user_subscriptions" in names and "update_user_memory" in names
    assert graph.FlowDeckAgent(None).user_store is None


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


# --- event layer: moved to ai_engine.processing, backend name still works ---


def test_backend_processing_is_the_moved_event_layer_with_backend_cache():
    import ai_engine.processing as moved
    import processing
    from ai_engine.processing import service as moved_service
    from processing.event import TickerEventSummary
    from services import platform_cache

    assert processing.get_ticker_event_summary is moved.get_ticker_event_summary
    assert TickerEventSummary is moved.TickerEventSummary
    # Importing the backend package plugs in its cache, so summaries stay cached.
    assert moved_service._cache["get_or_set"] is platform_cache.get_or_set

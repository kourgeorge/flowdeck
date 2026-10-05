"""Exercise the production lifecycle with fake graphs and isolated SQLite files."""

from __future__ import annotations

import gc
import sys
import threading
import weakref
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import database
import data_layer
import processing
from auth import get_current_admin_user, get_current_user
from models.db_models import Execution, Usage, User
from services import analysis_service, data_cache, report_service, token_service
from services.analysis_executor import AnalysisExecutor, AnalysisQueueFull


@pytest.fixture
def runtime(tmp_path, monkeypatch, request):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.sqlite'}", connect_args={"check_same_thread": False})
    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(report_service, "SessionLocal", sessions)
    monkeypatch.setattr(data_cache, "_store", data_cache._SQLiteTTLStore(str(tmp_path / "cache.sqlite"), 128))
    monkeypatch.setattr(config, "BUILD_ON_PRIOR_ANALYSIS", False)
    monkeypatch.setattr(config, "WRITE_AI_REPORTS_TO_RESULTS", False)
    gateway = SimpleNamespace(get_quote=lambda _ticker: {})
    monkeypatch.setattr(data_layer, "get_data_gateway", lambda: gateway)
    monkeypatch.setattr(processing, "get_ticker_event_summary", lambda *a, **kw: SimpleNamespace(event_score=0, dominant_events=[]))
    monkeypatch.setattr(analysis_service, "_has_sec_data", lambda _ticker: True)
    monkeypatch.setattr(analysis_service, "_has_fundamental_data", lambda _ticker: True)
    monkeypatch.setattr(analysis_service, "get_config_from_env", lambda _overrides: {})
    notify = Mock()
    monkeypatch.setattr(analysis_service, "notify_subscribers_new_report", notify)

    with sessions() as db:
        db.add(User(id=1, email="capacity-test@example.com", hashed_password="x"))
        db.commit()
        token_service.record_transaction(1, 10000, "initial_balance", db)

    rt = SimpleNamespace(
        sessions=sessions, created=[], closed=[], refs=[], releases=[],
        streams={}, init_error=None, notify=notify, gateway=gateway,
        workers=getattr(request, "param", 1),
    )

    class FakeGraph:
        def __init__(self, *, config, **kwargs):
            if rt.init_error:
                raise rt.init_error
            rt.created.append(len(rt.created) + 1)
            self.number = rt.created[-1]
            rt.refs.append(weakref.ref(self))
            self.config = config
            self.propagator = SimpleNamespace(
                create_initial_state=lambda ticker, date: {"ticker": ticker},
                get_graph_args=lambda **kw: {},
            )
            self.graph = SimpleNamespace(stream=self.stream)

        def stream(self, state, **kwargs):
            ticker = state["ticker"]
            if ticker in rt.streams:
                yield from rt.streams[ticker]()
            else:
                yield {}

        def close(self):
            rt.closed.append(self.number)

    monkeypatch.setattr(analysis_service, "TradingAgentsGraph", FakeGraph)
    executor = AnalysisExecutor(max_workers=rt.workers)
    rt.executor = executor
    rt.service = analysis_service.AnalysisService(str(tmp_path / "results"), executor=executor)

    def record(ticker, charged=False):
        with sessions() as db:
            if charged:
                ok, run_id = token_service.deduct_for_analysis(1, ticker, db)
                assert ok
                return run_id
            return token_service.record_analysis_run(1, ticker, db)

    def start(ticker, charged=False, callback=None):
        run_id = record(ticker, charged)
        rt.service.start_analysis(ticker, "2026-10-05", run_id, progress_callback=callback)
        return run_id

    def block(ticker):
        entered, release = threading.Event(), threading.Event()
        rt.releases.append(release)
        def stream():
            entered.set()
            assert release.wait(10), "Test did not release blocked analysis"
            yield {}
        rt.streams[ticker] = stream
        return entered, release

    def execution(run_id):
        with sessions() as db:
            row = db.get(Execution, run_id)
            return row.status, row.error_message

    def refunds(run_id):
        with sessions() as db:
            return [row.amount for row in db.query(Usage).filter_by(related_entity_id=run_id, transaction_type="refund").all()]

    rt.record, rt.start, rt.block, rt.execution, rt.refunds = record, start, block, execution, refunds
    yield rt
    for event in rt.releases:
        event.set()
    executor.shutdown(wait=True)
    engine.dispose()


@pytest.mark.parametrize("runtime", [1, 5], indirect=True)
def test_nine_run_batch_waits_before_graph_construction_and_releases_memory(runtime):
    rt = runtime
    blockers = [rt.block(f"T{i}") for i in range(rt.workers)]
    ids = [rt.start(f"T{i}") for i in range(9)]
    assert all(entered.wait(5) for entered, _release in blockers)
    # All slots run concurrently; the next job has no graph or LLM clients yet.
    assert len(rt.created) == rt.workers
    assert rt.service.get_analysis_status(ids[rt.workers])["status"] == "queued"
    assert rt.service.get_analysis_status(ids[-1])["status"] == "queued"
    assert data_cache.get_running_analysis_run_id_for_ticker("ticker", "T8") == ids[-1]
    assert len(data_cache.list_running_analyses("ticker")) == 9
    duplicate_id = rt.record("T8")
    assert rt.service.start_analysis("t8", "2026-10-05", duplicate_id) == (ids[-1], True)
    assert len(rt.service.running_analyses) == 9
    for _entered, release in blockers:
        release.set()
    rt.executor.shutdown(wait=True)
    assert len(rt.created) == len(rt.closed) == 9
    assert all(rt.execution(run_id)[0] == "completed" for run_id in ids)
    assert rt.service.running_analyses == {}
    assert data_cache.list_running_analyses("ticker") == []
    gc.collect()
    assert all(ref() is None for ref in rt.refs)


@pytest.mark.parametrize("failure_stage", ["setup", "stream"])
def test_failure_refunds_charge_once_and_releases_capacity(runtime, failure_stage):
    rt = runtime
    if failure_stage == "setup":
        rt.init_error = RuntimeError("test setup failure")
    else:
        def fail():
            raise RuntimeError("test stream failure")
            yield
        rt.streams["FAIL"] = fail
    run_id = rt.start("FAIL", charged=True)
    rt.executor.shutdown(wait=True)
    assert rt.execution(run_id)[0] == "failed"
    assert rt.refunds(run_id) == [token_service.COST_PER_ANALYSIS]
    with rt.sessions() as db:
        assert token_service.refund_for_failed_execution(run_id, db) is False
    assert rt.service.running_analyses == {}
    assert data_cache.get_analysis_status("ticker", run_id) is None
    assert len(rt.closed) == (0 if failure_stage == "setup" else 1)


def test_failed_uncharged_admin_run_does_not_mint_tokens(runtime):
    rt = runtime
    rt.init_error = RuntimeError("test setup failure")
    run_id = rt.start("ADMIN")
    rt.executor.shutdown(wait=True)
    assert rt.execution(run_id)[0] == "failed"
    assert rt.refunds(run_id) == []


def test_service_instances_share_process_capacity(runtime, monkeypatch, tmp_path):
    from services import analysis_executor
    rt = runtime
    monkeypatch.setattr(analysis_executor, "_executor", rt.executor)
    monkeypatch.setattr(analysis_executor, "_shutting_down", False)
    rt.service._executor = None
    other = analysis_service.AnalysisService(str(tmp_path / "other-results"))
    entered, release = rt.block("FIRST")
    rt.start("FIRST")
    assert entered.wait(5)
    run_id = rt.record("OTHER")
    other.start_analysis("OTHER", "2026-10-05", run_id)
    assert len(rt.created) == 1
    assert other.get_analysis_status(run_id)["status"] == "queued"
    release.set()
    rt.executor.shutdown(wait=True)
    assert len(rt.created) == 2
    assert other.running_analyses == rt.service.running_analyses == {}


def test_report_and_completion_callback_survive_state_cleanup(runtime):
    rt = runtime
    rt.streams["REPORT"] = lambda: iter([{"market_report": "Persisted analysis result", "market_score": 4}])
    completed = []
    def callback(chunk, info):
        if chunk.get("type") == "completed":
            completed.append(info["reports"]["market_report"])
    run_id = rt.start("REPORT", callback=callback)
    rt.executor.shutdown(wait=True)
    assert rt.execution(run_id)[0] == "completed"
    assert report_service.ReportService().get_reports_for_run(run_id)["market_report"] == "Persisted analysis result"
    assert completed == ["Persisted analysis result"]
    assert rt.service.running_analyses == {}


def test_cancel_queued_run_does_not_construct_graph_and_refunds(runtime):
    rt = runtime
    entered, release = rt.block("FIRST")
    rt.start("FIRST")
    assert entered.wait(5)
    cancelled = rt.start("SECOND", charged=True)
    data_cache.set_stop_requested(cancelled)
    release.set()
    rt.executor.shutdown(wait=True)
    assert len(rt.created) == 1
    assert rt.execution(cancelled) == ("failed", "Analysis cancelled before starting")
    assert rt.refunds(cancelled) == [token_service.COST_PER_ANALYSIS]
    assert not data_cache.get_stop_requested(cancelled)
    assert rt.service.running_analyses == {}


def test_cancel_running_run_cleans_up_and_refunds(runtime):
    rt = runtime
    entered, release = rt.block("ACTIVE")
    run_id = rt.start("ACTIVE", charged=True)
    assert entered.wait(5)
    data_cache.set_stop_requested(run_id)
    release.set()
    rt.executor.shutdown(wait=True)
    assert rt.execution(run_id) == ("failed", "Analysis cancelled")
    assert rt.refunds(run_id) == [token_service.COST_PER_ANALYSIS]
    assert len(rt.closed) == 1
    assert rt.service.running_analyses == {}


def test_shutdown_cancels_waiting_jobs_without_running_them(runtime):
    rt = runtime
    entered, release = rt.block("FIRST")
    rt.start("FIRST")
    assert entered.wait(5)
    queued = rt.start("WAITING", charged=True)
    rt.executor.shutdown(wait=False, cancel_futures=True)
    assert rt.execution(queued)[0] == "failed"
    assert rt.refunds(queued) == [token_service.COST_PER_ANALYSIS]
    assert queued not in rt.service.running_analyses
    assert data_cache.get_analysis_status("ticker", queued) is None
    release.set()
    rt.executor.shutdown(wait=True)
    assert len(rt.created) == 1


def test_closed_executor_does_not_leave_phantom_run_or_charge(runtime):
    rt = runtime
    rt.executor.shutdown(wait=True)
    run_id = rt.record("LATE", charged=True)
    with pytest.raises(RuntimeError, match="shutdown"):
        rt.service.start_analysis("LATE", "2026-10-05", run_id)
    assert rt.refunds(run_id) == [token_service.COST_PER_ANALYSIS]
    assert rt.execution(run_id)[0] == "failed"
    assert rt.service.running_analyses == {}
    assert data_cache.get_analysis_status("ticker", run_id) is None


def make_api(runtime, monkeypatch):
    import app_services
    from routers import analyses, admin
    monkeypatch.setattr(app_services, "get_analysis_service", lambda: runtime.service)
    # These routers may have been imported by another test before the fixture's
    # data_layer patch, so patch the lookup where the endpoint actually uses it.
    monkeypatch.setattr(analyses, "get_data_gateway", lambda: runtime.gateway)
    app = FastAPI()
    app.include_router(analyses.router)
    app.include_router(admin.router)
    user = SimpleNamespace(id=1, email="capacity-test@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_admin_user] = lambda: user
    def get_db():
        with runtime.sessions() as db:
            yield db
    app.dependency_overrides[database.get_db] = get_db
    return TestClient(app)


def test_api_queue_full_is_503_and_refunds_rejected_charge(runtime, monkeypatch):
    rt = runtime
    executor = AnalysisExecutor(max_workers=1, max_queued=0)
    rt.service._executor = executor
    entered, release = rt.block("FIRST")
    try:
        rt.start("FIRST")
        assert entered.wait(5)
        client = make_api(rt, monkeypatch)
        response = client.post("/api/analyses/start", json={"ticker": "REJECTED"})
        assert response.status_code == 503, response.text
        assert response.headers["Retry-After"] == "60"
        with rt.sessions() as db:
            rejected = db.query(Execution).filter_by(subject_id="REJECTED").one()
            assert rejected.status == "failed"
            assert rt.refunds(rejected.id) == [token_service.COST_PER_ANALYSIS]
        assert len(rt.created) == 1
        assert len(data_cache.list_running_analyses("ticker")) == 1
        assert client.post("/api/analyses/start", json={}).status_code == 400
    finally:
        release.set()
        executor.shutdown(wait=True)


def test_mission_control_batch_runs_automatically_with_bounded_concurrency(runtime, monkeypatch):
    from services import admin_service
    rt = runtime
    tickers = ["KKR", "CF", "MMM", "PNC", "JCI", "AHH", "AVNS", "AIP", "AMSF"]
    entered, release = rt.block(tickers[0])
    monkeypatch.setattr(admin_service, "load_mission_control_entries", lambda: [{"ticker": t} for t in tickers])
    response = make_api(rt, monkeypatch).post("/api/admin/mission-control/run", json={"tickers": tickers})
    assert response.status_code == 200, response.text
    assert entered.wait(5)
    body = response.json()
    assert len(body["triggered"]) == 9 and body["failed"] == []
    assert len(rt.created) == 1
    release.set()
    rt.executor.shutdown(wait=True)
    assert all(rt.execution(item["analysis_run_id"])[0] == "completed" for item in body["triggered"])
    assert rt.service.running_analyses == {}


def test_graph_close_closes_owned_clients_once_without_resetting_shared_chroma():
    from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    shared = Mock()
    memory_client = Mock()
    graph.deep_thinking_llm = graph.quick_thinking_llm = SimpleNamespace(root_client=shared)
    for attr in ("bull_memory", "bear_memory", "neutral_memory", "trader_memory", "invest_judge_memory"):
        setattr(graph, attr, SimpleNamespace(client=memory_client, chroma_client=Mock()))
    graph.close()
    shared.close.assert_called_once()
    memory_client.close.assert_called_once()
    graph.bull_memory.chroma_client.reset.assert_not_called()


def test_executor_recovers_capacity_after_task_failure():
    executor = AnalysisExecutor(max_workers=1, max_queued=0)
    release, callbacks_done = threading.Event(), threading.Event()
    try:
        def fail():
            assert release.wait(5)
            raise ValueError("intentional")
        future = executor.submit(fail)
        future.add_done_callback(lambda _done: callbacks_done.set())
        with pytest.raises(AnalysisQueueFull):
            executor.submit(lambda: 0)
        release.set()
        with pytest.raises(ValueError, match="intentional"):
            future.result(timeout=5)
        assert callbacks_done.wait(5)
        assert executor.submit(lambda: 42).result(timeout=5) == 42
    finally:
        release.set()
        executor.shutdown(wait=True)


@pytest.mark.parametrize("workers, queued", [(0, 2), (1, -1)])
def test_invalid_capacity_is_rejected(workers, queued):
    with pytest.raises(ValueError):
        AnalysisExecutor(workers, queued)


@pytest.mark.parametrize("queue_setting", [None, "unlimited", ""])
def test_default_queue_accepts_large_batch_with_only_five_active(monkeypatch, queue_setting):
    from services import analysis_executor

    monkeypatch.setattr(analysis_executor, "_executor", None)
    monkeypatch.setattr(analysis_executor, "_shutting_down", False)
    monkeypatch.delenv("FLOWDECK_ANALYSIS_WORKERS", raising=False)
    if queue_setting is None:
        monkeypatch.delenv("FLOWDECK_ANALYSIS_QUEUE_SIZE", raising=False)
    else:
        monkeypatch.setenv("FLOWDECK_ANALYSIS_QUEUE_SIZE", queue_setting)
    executor = analysis_executor.get_analysis_executor()
    release, five_active = threading.Event(), threading.Event()
    lock = threading.Lock()
    active = peak = 0
    started = []

    def work(index):
        nonlocal active, peak
        with lock:
            started.append(index)
            active += 1
            peak = max(peak, active)
            if active == 5:
                five_active.set()
        try:
            assert release.wait(5)
            return index
        finally:
            with lock:
                active -= 1

    try:
        futures = [executor.submit(work, index) for index in range(100)]
        assert five_active.wait(5)
        with lock:
            assert active == len(started) == 5
        assert len(futures) == 100  # All 95 waiting jobs were accepted.
        release.set()
        assert [future.result(timeout=5) for future in futures] == list(range(100))
        assert peak == 5
    finally:
        release.set()
        executor.shutdown(wait=True)

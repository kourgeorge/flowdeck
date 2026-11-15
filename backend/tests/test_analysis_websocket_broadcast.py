"""Analysis WebSocket progress: sent from worker threads, to every viewer, with a real end frame."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from routers import analyses


class FakeSocket:
    def __init__(self, fail=False):
        self.sent = []
        self.loops = []
        self.fail = fail

    async def send_json(self, message):
        self.loops.append(asyncio.get_running_loop())
        if self.fail:
            raise RuntimeError("socket closed")
        await asyncio.sleep(0)  # yield like a real transport, so ordering is exercised
        self.sent.append(message)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(analyses, "active_connections", {})
    monkeypatch.setattr(analyses, "_send_locks", {})
    monkeypatch.setattr(analyses, "_main_loop", None)


def _info(run_id=7, status="running"):
    return {"analysis_run_id": run_id, "ticker": "AAPL", "date": "2026-11-16",
            "status": status, "agent_statuses": {"Market Analyst": "in_progress"}}


async def _drain():
    for _ in range(50):
        await asyncio.sleep(0)


def _run_callbacks_in_pool(calls):
    """Fire callbacks from a worker pool thread, as the analysis executor does."""
    def worker():
        assert threading.current_thread() is not threading.main_thread()
        for chunk, info in calls:
            analyses.progress_callback(chunk, info)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()


def test_every_send_from_a_pool_thread_arrives_on_the_main_loop():
    async def scenario():
        analyses.remember_main_loop()
        main_loop = asyncio.get_running_loop()
        ws = FakeSocket()
        analyses.add_connection("7", ws)
        calls = [({"step": i}, _info()) for i in range(5)]
        await asyncio.to_thread(_run_callbacks_in_pool, calls)
        await _drain()
        assert [m["data"]["chunk"] for m in ws.sent] == [str({"step": i}) for i in range(5)]
        assert all(loop is main_loop for loop in ws.loops)
        # Calling again from another pool thread still works (the old code closed its loop).
        await asyncio.to_thread(_run_callbacks_in_pool, [({"step": 5}, _info())])
        await _drain()
        assert len(ws.sent) == 6
    asyncio.run(scenario())


def test_two_viewers_both_get_progress_and_one_leaving_keeps_the_other():
    async def scenario():
        analyses.remember_main_loop()
        a, b = FakeSocket(), FakeSocket()
        analyses.add_connection("7", a)
        analyses.add_connection("7", b)
        await asyncio.to_thread(_run_callbacks_in_pool, [({"step": 1}, _info())])
        await _drain()
        assert len(a.sent) == len(b.sent) == 1
        assert a.sent[0]["type"] == "progress" and a.sent[0]["data"]["status"] == "running"

        analyses.remove_connection("7", a)
        await asyncio.to_thread(_run_callbacks_in_pool, [({"step": 2}, _info())])
        await _drain()
        assert len(a.sent) == 1
        assert len(b.sent) == 2
    asyncio.run(scenario())


def test_dead_socket_is_dropped_and_others_still_receive():
    async def scenario():
        analyses.remember_main_loop()
        dead, alive = FakeSocket(fail=True), FakeSocket()
        analyses.add_connection("7", dead)
        analyses.add_connection("7", alive)
        await asyncio.to_thread(_run_callbacks_in_pool, [({"step": 1}, _info())])
        await _drain()
        assert analyses.active_connections["7"] == {alive}
        assert len(alive.sent) == 1
    asyncio.run(scenario())


def test_completion_sends_top_level_completed_frame_after_progress():
    async def scenario():
        analyses.remember_main_loop()
        ws = FakeSocket()
        analyses.add_connection("7", ws)
        calls = [({"step": 1}, _info()), ({"type": "completed"}, _info(status="completed"))]
        await asyncio.to_thread(_run_callbacks_in_pool, calls)
        await _drain()
        assert [m["type"] for m in ws.sent] == ["progress", "progress", "completed"]
        assert ws.sent[-1]["data"] == {"analysis_run_id": 7, "ticker": "AAPL",
                                       "date": "2026-11-16", "status": "completed"}
    asyncio.run(scenario())


def test_failure_sends_top_level_failed_frame():
    frames = analyses.build_progress_frames({"type": "error", "error": "boom"}, _info(status="error"))
    assert frames[0]["type"] == "progress"
    assert frames[-1] == {"type": "failed", "data": {"analysis_run_id": 7, "ticker": "AAPL",
                                                     "date": "2026-11-16", "status": "failed",
                                                     "error": "boom"}}
    cancelled = analyses.build_progress_frames({"type": "error", "error": "stop"}, _info(status="cancelled"))
    assert cancelled[-1]["data"]["status"] == "cancelled"


def test_no_loop_or_viewers_is_a_quiet_no_op():
    analyses.progress_callback({"step": 1}, _info())  # no loop captured yet
    analyses.remove_connection("7", FakeSocket())  # removing unknown socket is harmless

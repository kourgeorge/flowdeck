from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import data_cache


class TestDataCacheSingleFlight(unittest.TestCase):
    def setUp(self) -> None:
        self._original_store = data_cache._store
        data_cache._store = data_cache._TTLStore(maxsize=128)
        data_cache.clear_cache()

    def tearDown(self) -> None:
        data_cache.clear_cache()
        data_cache._store = self._original_store

    def test_get_cached_singleflight_dedupes_concurrent_fetches(self) -> None:
        started = threading.Event()
        release = threading.Event()
        fetch_calls = 0
        fetch_lock = threading.Lock()
        results: list[dict] = []
        errors: list[BaseException] = []

        def fetch() -> dict:
            nonlocal fetch_calls
            with fetch_lock:
                fetch_calls += 1
            started.set()
            self.assertTrue(release.wait(2.0), "Timed out waiting to release leader fetch")
            return {"value": 42}

        def worker() -> None:
            try:
                results.append(data_cache.get_cached("sf:key", 60, fetch))
            except BaseException as exc:  # pragma: no cover - asserted via errors collection
                errors.append(exc)

        leader = threading.Thread(target=worker)
        follower = threading.Thread(target=worker)

        leader.start()
        self.assertTrue(started.wait(2.0), "Leader fetch did not start in time")
        follower.start()
        time.sleep(0.05)
        release.set()

        leader.join(2.0)
        follower.join(2.0)

        self.assertFalse(errors)
        self.assertEqual(fetch_calls, 1)
        self.assertEqual(results, [{"value": 42}, {"value": 42}])

    def test_get_cached_batch_singleflight_dedupes_concurrent_fetches(self) -> None:
        started = threading.Event()
        release = threading.Event()
        batch_calls = 0
        batch_lock = threading.Lock()
        results: list[dict] = []
        errors: list[BaseException] = []

        def batch_fetch(keys: list[str]) -> dict:
            nonlocal batch_calls
            with batch_lock:
                batch_calls += 1
            self.assertEqual(keys, ["sf:batch"])
            started.set()
            self.assertTrue(release.wait(2.0), "Timed out waiting to release leader batch fetch")
            return {"sf:batch": {"value": 99}}

        def worker() -> None:
            try:
                results.append(data_cache.get_cached_batch([("sf:batch", 60)], batch_fetch))
            except BaseException as exc:  # pragma: no cover - asserted via errors collection
                errors.append(exc)

        leader = threading.Thread(target=worker)
        follower = threading.Thread(target=worker)

        leader.start()
        self.assertTrue(started.wait(2.0), "Leader batch fetch did not start in time")
        follower.start()
        time.sleep(0.05)
        release.set()

        leader.join(2.0)
        follower.join(2.0)

        self.assertFalse(errors)
        self.assertEqual(batch_calls, 1)
        self.assertEqual(results, [{"sf:batch": {"value": 99}}, {"sf:batch": {"value": 99}}])

    def test_get_cached_clears_inflight_after_failure(self) -> None:
        started = threading.Event()
        release = threading.Event()
        fetch_calls = 0
        fetch_lock = threading.Lock()
        errors: list[BaseException] = []

        def failing_fetch() -> dict:
            nonlocal fetch_calls
            with fetch_lock:
                fetch_calls += 1
            started.set()
            self.assertTrue(release.wait(2.0), "Timed out waiting to release failing leader fetch")
            raise RuntimeError("boom")

        def worker() -> None:
            try:
                data_cache.get_cached("sf:error", 60, failing_fetch)
            except BaseException as exc:
                errors.append(exc)

        leader = threading.Thread(target=worker)
        follower = threading.Thread(target=worker)

        leader.start()
        self.assertTrue(started.wait(2.0), "Failing leader fetch did not start in time")
        follower.start()
        time.sleep(0.05)
        release.set()

        leader.join(2.0)
        follower.join(2.0)

        self.assertEqual(fetch_calls, 1)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(isinstance(exc, RuntimeError) for exc in errors))

        retry_calls = 0

        def succeeding_fetch() -> dict:
            nonlocal retry_calls
            retry_calls += 1
            return {"value": "ok"}

        retry_result = data_cache.get_cached("sf:error", 60, succeeding_fetch)
        self.assertEqual(retry_calls, 1)
        self.assertEqual(retry_result, {"value": "ok"})

    def test_get_cached_with_origin_recovers_when_leader_is_wedged(self) -> None:
        started = threading.Event()
        leader_release = threading.Event()

        def wedged_fetch() -> dict:
            started.set()
            leader_release.wait(5.0)
            return {"value": "leader-too-slow"}

        leader = threading.Thread(
            target=data_cache.get_cached, args=("sf:wedged", 60, wedged_fetch), daemon=True
        )
        leader.start()
        self.assertTrue(started.wait(2.0), "Leader fetch did not start in time")

        original_timeout = data_cache._FOLLOWER_WAIT_TIMEOUT_SEC
        data_cache._FOLLOWER_WAIT_TIMEOUT_SEC = 0.2
        self.addCleanup(setattr, data_cache, "_FOLLOWER_WAIT_TIMEOUT_SEC", original_timeout)

        fallback_calls = 0

        def fallback_fetch() -> dict:
            nonlocal fallback_calls
            fallback_calls += 1
            return {"value": "fallback"}

        value, from_cache = data_cache.get_cached_with_origin("sf:wedged", 60, fallback_fetch)

        self.assertEqual(value, {"value": "fallback"})
        self.assertFalse(from_cache)
        self.assertEqual(fallback_calls, 1)
        self.assertNotIn("sf:wedged", data_cache._inflight_calls)

        leader_release.set()
        leader.join(2.0)

    def test_get_cached_batch_omits_wedged_key(self) -> None:
        started = threading.Event()
        leader_release = threading.Event()

        def wedged_batch_fetch(keys: list[str]) -> dict:
            started.set()
            leader_release.wait(5.0)
            return {k: {"value": "leader-too-slow"} for k in keys}

        leader = threading.Thread(
            target=data_cache.get_cached_batch,
            args=([("sf:batch-wedged", 60)], wedged_batch_fetch),
            daemon=True,
        )
        leader.start()
        self.assertTrue(started.wait(2.0), "Leader batch fetch did not start in time")

        original_timeout = data_cache._FOLLOWER_WAIT_TIMEOUT_SEC
        data_cache._FOLLOWER_WAIT_TIMEOUT_SEC = 0.2
        self.addCleanup(setattr, data_cache, "_FOLLOWER_WAIT_TIMEOUT_SEC", original_timeout)

        def batch_fetch(keys: list[str]) -> dict:
            return {k: {"value": "ok"} for k in keys if k != "sf:batch-wedged"}

        result = data_cache.get_cached_batch(
            [("sf:batch-wedged", 60), ("sf:batch-ok", 60)], batch_fetch
        )

        self.assertNotIn("sf:batch-wedged", result)
        self.assertEqual(result.get("sf:batch-ok"), {"value": "ok"})
        self.assertNotIn("sf:batch-wedged", data_cache._inflight_calls)

        leader_release.set()
        leader.join(2.0)


if __name__ == "__main__":
    unittest.main()

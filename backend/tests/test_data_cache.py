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


if __name__ == "__main__":
    unittest.main()

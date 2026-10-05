"""Limit active ticker analyses, with an optional cap on lightweight queued jobs."""

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Optional


class AnalysisQueueFull(RuntimeError):
    """The server cannot accept another analysis yet."""


class AnalysisExecutor:
    def __init__(self, max_workers: int = 5, max_queued: Optional[int] = None):
        if max_workers < 1 or (max_queued is not None and max_queued < 0):
            raise ValueError("Analysis workers must be >= 1; queue size must be >= 0 or None")
        self._slots = (
            threading.BoundedSemaphore(max_workers + max_queued)
            if max_queued is not None else None
        )
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ticker-analysis"
        )

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        # Jobs contain only request parameters until a worker starts them. The
        # default queue accepts the whole batch; deployments can opt into a cap.
        slots = self._slots
        if slots is not None and not slots.acquire(blocking=False):
            raise AnalysisQueueFull("Analysis queue is full. Please try again later.")
        try:
            future = self._pool.submit(fn, *args, **kwargs)
        except BaseException:
            if slots is not None:
                slots.release()
            raise
        if slots is not None:
            future.add_done_callback(lambda _future: slots.release())
        return future

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


_executor: Optional[AnalysisExecutor] = None
_executor_lock = threading.Lock()
_shutting_down = False


def get_analysis_executor() -> AnalysisExecutor:
    """All AnalysisService instances in this process share the same budget.

    Production should use one Uvicorn worker on a 4 GiB host. Multiple worker
    processes each have their own budget; this is not a distributed queue.
    """
    global _executor
    with _executor_lock:
        if _shutting_down:
            raise RuntimeError("Analysis service is shutting down")
        if _executor is None:
            queue_size = os.environ.get("FLOWDECK_ANALYSIS_QUEUE_SIZE", "unlimited").strip().lower()
            _executor = AnalysisExecutor(
                max_workers=int(os.environ.get("FLOWDECK_ANALYSIS_WORKERS", "5")),
                max_queued=None if queue_size in ("", "unlimited") else int(queue_size),
            )
        return _executor


def shutdown_analysis_executor() -> None:
    global _shutting_down
    with _executor_lock:
        _shutting_down = True
        executor = _executor
    if executor is not None:
        executor.shutdown(wait=False, cancel_futures=True)

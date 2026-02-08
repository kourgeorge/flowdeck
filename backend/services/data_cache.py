"""
Generic TTL cache for third-party data fetch results.

Supports per-key TTL with an in-memory store. Thread-safe for use in async FastAPI context.
"""

from __future__ import annotations

import time
import threading
from typing import Callable, Dict, List, Optional, Tuple, TypeVar

T = TypeVar("T")


class _TTLStore:
    """In-memory store with per-key TTL. LRU eviction when maxsize is reached."""

    def __init__(self, maxsize: int):
        self._maxsize = maxsize
        self._data: dict[str, Tuple[T, float]] = {}  # key -> (value, expires_at)
        self._order: list[str] = []  # LRU order
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[T]:
        with self._lock:
            if key not in self._data:
                return None
            value, expires_at = self._data[key]
            if time.monotonic() >= expires_at:
                del self._data[key]
                self._order.remove(key)
                return None
            # Move to end for LRU
            self._order.remove(key)
            self._order.append(key)
            return value

    def set(self, key: str, value: T, ttl_seconds: float) -> None:
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            if key in self._data:
                self._order.remove(key)
            elif len(self._data) >= self._maxsize and self._order:
                # Evict oldest
                oldest = self._order.pop(0)
                del self._data[oldest]
            self._data[key] = (value, expires_at)
            self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()


_store: Optional[_TTLStore] = None


def _get_store() -> _TTLStore:
    """Get or create the shared store."""
    global _store
    if _store is None:
        from config import DATA_CACHE_MAX_SIZE
        _store = _TTLStore(maxsize=DATA_CACHE_MAX_SIZE)
    return _store


def get_cached(
    key: str,
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
) -> T:
    """
    Return cached value if present and not expired; otherwise call fetch_fn, store, and return.

    Args:
        key: Cache key string.
        ttl_seconds: TTL in seconds for this entry.
        fetch_fn: Callable that returns the value on cache miss.

    Returns:
        The cached or freshly fetched value.
    """
    from config import DATA_CACHE_ENABLED

    if not DATA_CACHE_ENABLED:
        return fetch_fn()

    store = _get_store()
    cached = store.get(key)
    if cached is not None:
        return cached

    value = fetch_fn()
    store.set(key, value, ttl_seconds)
    return value


def get_cached_batch(
    key_ttl_pairs: List[Tuple[str, float]],
    batch_fetch_fn: Callable[[List[str]], Dict[str, T]],
) -> Dict[str, T]:
    """
    Get multiple values from cache; on miss, call batch_fetch_fn(missing_keys) and cache results.

    Args:
        key_ttl_pairs: List of (cache_key, ttl_seconds).
        batch_fetch_fn: Called with list of keys that missed; returns dict key -> value.

    Returns:
        Dict key -> value (from cache or batch fetch).
    """
    from config import DATA_CACHE_ENABLED

    if not DATA_CACHE_ENABLED:
        keys = [k for k, _ in key_ttl_pairs]
        return batch_fetch_fn(keys)

    store = _get_store()
    ttl_by_key = {k: ttl for k, ttl in key_ttl_pairs}
    result: Dict[str, T] = {}
    missing: List[str] = []
    for key, ttl in key_ttl_pairs:
        val = store.get(key)
        if val is not None:
            result[key] = val
        else:
            missing.append(key)
    if missing:
        fetched = batch_fetch_fn(missing)
        for k, v in fetched.items():
            result[k] = v
            if v is not None:
                store.set(k, v, ttl_by_key[k])
    return result


def init_cache(maxsize: int) -> _TTLStore:
    """Initialize the module-level cache. Called at startup."""
    global _store
    _store = _TTLStore(maxsize=maxsize)
    return _store


def clear_cache() -> None:
    """Clear all cached entries. Useful for testing."""
    global _store
    if _store is not None:
        _store.clear()

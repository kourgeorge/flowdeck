"""
Generic TTL cache and running process status in a single SQLite file.

Supports per-key TTL cache (quotes, company info, etc.) and analysis/process status
(type + run_id) so data persists and is shared across workers. Thread-safe.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

T = TypeVar("T")


def _cache_dumps(obj: Any) -> str:
    """JSON encode cache values; support datetime/date for API responses."""
    if obj is None:
        return "null"

    class _Encoder(json.JSONEncoder):
        def default(self, o: Any) -> Any:
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            return json.JSONEncoder.default(self, o)

    return json.dumps(obj, cls=_Encoder)


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
            self._order.remove(key)
            self._order.append(key)
            return value

    def set(self, key: str, value: T, ttl_seconds: float) -> None:
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            if key in self._data:
                self._order.remove(key)
            elif len(self._data) >= self._maxsize and self._order:
                oldest = self._order.pop(0)
                del self._data[oldest]
            self._data[key] = (value, expires_at)
            self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._order.clear()


class _SQLiteTTLStore:
    """SQLite-backed TTL store and analysis status. One connection per thread (safe with asyncio.to_thread)."""

    _DATA_CACHE_TABLE = "data_cache"
    _ANALYSIS_STATUS_TABLE = "analysis_status"

    def __init__(self, path: str, maxsize: int):
        self._path = path
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._local = threading.local()

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            parent = Path(self._path).parent
            if parent:
                parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._path, timeout=10.0)
            conn.execute("PRAGMA busy_timeout=10000")
            self._ensure_tables(conn)
            self._local.conn = conn
        return conn

    def _ensure_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._DATA_CACHE_TABLE} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._ANALYSIS_STATUS_TABLE} (
                type TEXT NOT NULL,
                run_id INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (type, run_id)
            )
            """
        )
        conn.commit()
        now = time.time()
        conn.execute(
            f"DELETE FROM {self._DATA_CACHE_TABLE} WHERE expires_at <= ?", (now,)
        )
        conn.commit()

    def get(self, key: str) -> Optional[T]:
        with self._lock:
            conn = self._connection()
            row = conn.execute(
                f"SELECT value, expires_at FROM {self._DATA_CACHE_TABLE} WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value_json, expires_at = row
            if time.time() >= expires_at:
                conn.execute(f"DELETE FROM {self._DATA_CACHE_TABLE} WHERE key = ?", (key,))
                conn.commit()
                return None
            return json.loads(value_json)

    def get_raw(self, key: str) -> Optional[T]:
        """Return cached value if present, ignoring TTL. For fallback when primary fetch fails."""
        with self._lock:
            conn = self._connection()
            row = conn.execute(
                f"SELECT value FROM {self._DATA_CACHE_TABLE} WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row[0])

    def set(self, key: str, value: T, ttl_seconds: float) -> None:
        with self._lock:
            conn = self._connection()
            expires_at = time.time() + ttl_seconds
            value_json = _cache_dumps(value)
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {self._DATA_CACHE_TABLE} (key, value, expires_at)
                VALUES (?, ?, ?)
                """,
                (key, value_json, expires_at),
            )
            conn.commit()
            now = time.time()
            conn.execute(
                f"DELETE FROM {self._DATA_CACHE_TABLE} WHERE expires_at <= ?", (now,)
            )
            conn.commit()
            count = conn.execute(
                f"SELECT count(*) FROM {self._DATA_CACHE_TABLE}"
            ).fetchone()[0]
            while count > self._maxsize:
                conn.execute(
                    f"""
                    DELETE FROM {self._DATA_CACHE_TABLE}
                    WHERE key = (
                        SELECT key FROM {self._DATA_CACHE_TABLE}
                        ORDER BY expires_at ASC
                        LIMIT 1
                    )
                    """
                )
                conn.commit()
                count = conn.execute(
                    f"SELECT count(*) FROM {self._DATA_CACHE_TABLE}"
                ).fetchone()[0]

    def clear(self) -> None:
        with self._lock:
            conn = self._connection()
            conn.execute(f"DELETE FROM {self._DATA_CACHE_TABLE}")
            conn.commit()

    def get_analysis_status(self, type_name: str, run_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._connection()
            row = conn.execute(
                f"SELECT payload FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ? AND run_id = ?",
                (type_name, run_id),
            ).fetchone()
            if row is None:
                return None
            return json.loads(row[0])

    def set_analysis_status(self, type_name: str, run_id: int, data: Dict[str, Any]) -> None:
        with self._lock:
            conn = self._connection()
            payload = _cache_dumps(data)
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {self._ANALYSIS_STATUS_TABLE} (type, run_id, payload)
                VALUES (?, ?, ?)
                """,
                (type_name, run_id, payload),
            )
            conn.commit()

    def delete_analysis_status(self, type_name: str, run_id: int) -> None:
        with self._lock:
            conn = self._connection()
            conn.execute(
                f"DELETE FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ? AND run_id = ?",
                (type_name, run_id),
            )
            conn.commit()

    def get_running_analysis_run_id_for_ticker(self, type_name: str, ticker: str) -> Optional[int]:
        """Return analysis_run_id for a running analysis of this ticker, or None."""
        with self._lock:
            conn = self._connection()
            rows = conn.execute(
                f"SELECT run_id, payload FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ?",
                (type_name,),
            ).fetchall()
            ticker_upper = ticker.upper()
            for run_id, payload_json in rows:
                data = json.loads(payload_json)
                if data.get("status") == "running" and (data.get("ticker") or "").upper() == ticker_upper:
                    return run_id
            return None

    def list_running_analyses(self, type_name: str) -> List[Dict[str, Any]]:
        """Return all running status rows for this type. Each dict has run_id plus payload fields."""
        with self._lock:
            conn = self._connection()
            rows = conn.execute(
                f"SELECT run_id, payload FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ?",
                (type_name,),
            ).fetchall()
            result: List[Dict[str, Any]] = []
            for run_id, payload_json in rows:
                data = json.loads(payload_json)
                if data.get("status") != "running":
                    continue
                out = dict(data)
                out["analysis_run_id"] = run_id
                result.append(out)
            return result

    _STOP_REQUEST_TYPE = "stop_request"

    def set_stop_requested(self, run_id: int) -> None:
        """Record that this run_id was requested to stop (so the analysis thread can exit)."""
        with self._lock:
            conn = self._connection()
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {self._ANALYSIS_STATUS_TABLE} (type, run_id, payload)
                VALUES (?, ?, ?)
                """,
                (self._STOP_REQUEST_TYPE, run_id, "{}"),
            )
            conn.commit()

    def get_stop_requested(self, run_id: int) -> bool:
        """Return True if stop was requested for this run_id."""
        with self._lock:
            conn = self._connection()
            row = conn.execute(
                f"SELECT 1 FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ? AND run_id = ?",
                (self._STOP_REQUEST_TYPE, run_id),
            ).fetchone()
            return row is not None

    def clear_stop_requested(self, run_id: int) -> None:
        """Clear the stop request for this run_id (e.g. after analysis has exited)."""
        with self._lock:
            conn = self._connection()
            conn.execute(
                f"DELETE FROM {self._ANALYSIS_STATUS_TABLE} WHERE type = ? AND run_id = ?",
                (self._STOP_REQUEST_TYPE, run_id),
            )
            conn.commit()


_store: Optional[Union[_TTLStore, _SQLiteTTLStore]] = None


def _get_store() -> Union[_TTLStore, _SQLiteTTLStore]:
    """Get or create the shared store."""
    global _store
    if _store is None:
        from config import DATA_CACHE_MAX_SIZE, DATA_CACHE_PATH
        _store = _SQLiteTTLStore(path=DATA_CACHE_PATH, maxsize=DATA_CACHE_MAX_SIZE)
    return _store


def ensure_data_cache() -> None:
    """Initialize the shared SQLite store if needed. Call at app startup so analysis status is visible to all workers."""
    _get_store()


def get_cached_raw(key: str) -> Optional[T]:
    """Return cached value if present, ignoring TTL. For fallback when fetch fails."""
    from config import DATA_CACHE_ENABLED
    if not DATA_CACHE_ENABLED:
        return None
    store = _get_store()
    if hasattr(store, "get_raw"):
        return store.get_raw(key)
    return None


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
    value, _ = get_cached_with_origin(key, ttl_seconds, fetch_fn)
    return value


def get_cached_with_origin(
    key: str,
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
) -> Tuple[T, bool]:
    """
    Like get_cached but returns (value, from_cache).
    from_cache is True if the value was served from cache, False if fetch_fn was called.
    """
    from config import DATA_CACHE_ENABLED

    if not DATA_CACHE_ENABLED:
        return (fetch_fn(), False)

    store = _get_store()
    cached = store.get(key)
    if cached is not None:
        return (cached, True)

    value = fetch_fn()
    store.set(key, value, ttl_seconds)
    return (value, False)


def refresh_cached(
    key: str,
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
) -> T:
    """
    Always run fetch_fn, store the result in cache with the given TTL, and return it.
    Use for periodic cache warming so data is fresh before the next request.
    """
    from config import DATA_CACHE_ENABLED

    value = fetch_fn()
    if DATA_CACHE_ENABLED:
        store = _get_store()
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


def init_cache(maxsize: int) -> Union[_TTLStore, _SQLiteTTLStore]:
    """Initialize the module-level cache. Called at startup or for tests."""
    global _store
    from config import DATA_CACHE_PATH
    _store = _SQLiteTTLStore(path=DATA_CACHE_PATH, maxsize=maxsize)
    return _store


def clear_cache() -> None:
    """Clear all TTL cache entries. Useful for testing. Does not clear analysis_status."""
    global _store
    if _store is not None:
        _store.clear()


def get_analysis_status(type_name: str, run_id: int) -> Optional[Dict[str, Any]]:
    """Get status of a running process by type and run_id. Returns None if not found."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        return store.get_analysis_status(type_name, run_id)
    return None


def set_analysis_status(type_name: str, run_id: int, data: Dict[str, Any]) -> None:
    """Upsert status for a running process (e.g. type='ticker', run_id=analysis_run_id)."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        store.set_analysis_status(type_name, run_id, data)


def delete_analysis_status(type_name: str, run_id: int) -> None:
    """Remove status when process completes or errors."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        store.delete_analysis_status(type_name, run_id)


def get_running_analysis_run_id_for_ticker(type_name: str, ticker: str) -> Optional[int]:
    """Return run_id for a running analysis of this ticker, or None. Used to show progress in UI."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        return store.get_running_analysis_run_id_for_ticker(type_name, ticker)
    return None


def list_running_analyses(type_name: str) -> List[Dict[str, Any]]:
    """Return all running analyses for this type (e.g. 'ticker'). For admin UI."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        return store.list_running_analyses(type_name)
    return []


def set_stop_requested(run_id: int) -> None:
    """Record that this run_id was requested to stop (so the analysis thread can exit)."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        store.set_stop_requested(run_id)


def get_stop_requested(run_id: int) -> bool:
    """Return True if stop was requested for this run_id."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        return store.get_stop_requested(run_id)
    return False


def clear_stop_requested(run_id: int) -> None:
    """Clear the stop request for this run_id (e.g. after analysis has exited)."""
    store = _get_store()
    if isinstance(store, _SQLiteTTLStore):
        store.clear_stop_requested(run_id)

"""
Shared platform cache helpers for raw data, derived processing outputs, and report snapshots.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence, Tuple, TypeVar

try:
    from services.data_cache import get_cached, get_cached_with_origin, refresh_cached
except ModuleNotFoundError:  # pragma: no cover - package-style import path
    from backend.services.data_cache import get_cached, get_cached_with_origin, refresh_cached

T = TypeVar("T")

_PLATFORM_CACHE_PREFIX = "platform"


def _normalize_cache_part(part: Any) -> str:
    if part is None:
        return "-"
    if isinstance(part, bool):
        return "true" if part else "false"
    if isinstance(part, (list, tuple)):
        return ",".join(_normalize_cache_part(item) for item in part)
    text = str(part).strip()
    if not text:
        return "-"
    return text.replace(":", "_")


def make_cache_key(namespace: str, *parts: Any, version: str = "v1") -> str:
    """Build a stable namespaced cache key for platform-level reuse."""
    segments = [_PLATFORM_CACHE_PREFIX, _normalize_cache_part(namespace), _normalize_cache_part(version)]
    segments.extend(_normalize_cache_part(part) for part in parts)
    return ":".join(segments)


def get_or_set(
    namespace: str,
    *,
    parts: Sequence[Any],
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
    version: str = "v1",
) -> T:
    """Get a cached value or compute and cache it under a namespaced key."""
    key = make_cache_key(namespace, *parts, version=version)
    return get_cached(key, ttl_seconds, fetch_fn)


def get_or_set_with_origin(
    namespace: str,
    *,
    parts: Sequence[Any],
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
    version: str = "v1",
) -> Tuple[T, bool]:
    """Like get_or_set, but also indicate whether the value came from cache."""
    key = make_cache_key(namespace, *parts, version=version)
    return get_cached_with_origin(key, ttl_seconds, fetch_fn)


def refresh(
    namespace: str,
    *,
    parts: Sequence[Any],
    ttl_seconds: float,
    fetch_fn: Callable[[], T],
    version: str = "v1",
) -> T:
    """Force-refresh a namespaced cache entry."""
    key = make_cache_key(namespace, *parts, version=version)
    return refresh_cached(key, ttl_seconds, fetch_fn)

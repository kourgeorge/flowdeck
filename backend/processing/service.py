"""Plugs the backend cache into the event layer, which now lives in ai_engine.processing."""

from __future__ import annotations

try:
    from config import PROCESSING_CACHE_TTL_TICKER_EVENTS
    from services.data_cache import get_cached_raw
    from services.platform_cache import get_or_set, make_cache_key
except ModuleNotFoundError:  # pragma: no cover - package-style import path
    from backend.config import PROCESSING_CACHE_TTL_TICKER_EVENTS
    from backend.services.data_cache import get_cached_raw
    from backend.services.platform_cache import get_or_set, make_cache_key

from ai_engine.processing.service import (  # noqa: F401
    configure_event_cache,
    get_cached_ticker_event_summary,
    get_ticker_event_summary,
    warm_ticker_event_summary_async,
)

configure_event_cache(
    get_or_set=get_or_set,
    get_cached_raw=get_cached_raw,
    make_cache_key=make_cache_key,
    ttl_seconds=PROCESSING_CACHE_TTL_TICKER_EVENTS,
)

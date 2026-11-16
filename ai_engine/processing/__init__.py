"""Event layer: deterministic ticker events and their digest projection.

Lives in ai_engine because the brief and stocks discovery use it and ai_engine may not
import backend code. backend.processing re-exports it and plugs in the backend cache.
"""

from .event import (
    DetectedEvent,
    EventDomain,
    EventStrength,
    TickerEventSummary,
    extract_fundamental_events,
    extract_insider_events,
    parse_rsi_indicator_data,
    extract_price_technical_events,
    extract_ticker_events,
)
from .digest_projection import ImportantEvent, build_important_events
from .service import (
    configure_event_cache,
    get_cached_ticker_event_summary,
    get_ticker_event_summary,
    warm_ticker_event_summary_async,
)

__all__ = [
    "DetectedEvent",
    "EventDomain",
    "EventStrength",
    "ImportantEvent",
    "TickerEventSummary",
    "build_important_events",
    "configure_event_cache",
    "extract_fundamental_events",
    "extract_insider_events",
    "parse_rsi_indicator_data",
    "extract_price_technical_events",
    "extract_ticker_events",
    "get_cached_ticker_event_summary",
    "get_ticker_event_summary",
    "warm_ticker_event_summary_async",
]

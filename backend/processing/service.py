"""Cached processing services built on top of normalized backend data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Dict, List, Optional

try:
    from config import PROCESSING_CACHE_TTL_TICKER_EVENTS
    from services.data_cache import get_cached_raw
    from services.platform_cache import get_or_set, make_cache_key
except ModuleNotFoundError:  # pragma: no cover - package-style import path
    from backend.config import PROCESSING_CACHE_TTL_TICKER_EVENTS
    from backend.services.data_cache import get_cached_raw
    from backend.services.platform_cache import get_or_set, make_cache_key

from .event import TickerEventSummary, extract_ticker_events, parse_rsi_indicator_data

_TICKER_EVENT_CACHE_NAMESPACE = "processing:ticker_events"
_TICKER_EVENT_CACHE_VERSION = "v1"
_TICKER_EVENT_WARMER = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ticker-event-summary")
_TICKER_EVENT_WARMING_KEYS: set[str] = set()
_TICKER_EVENT_WARMING_LOCK = Lock()


def _ticker_event_cache_parts(
    ticker: str,
    *,
    as_of_date: str,
    history_period: str,
    history_interval: str,
    insider_limit: int,
    rsi_look_back_days: int,
    price_technical_lookback_days: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> List[Any]:
    return [
        ticker.upper(),
        as_of_date,
        history_period,
        history_interval,
        start_date or "-",
        end_date or "-",
        insider_limit,
        rsi_look_back_days,
        price_technical_lookback_days,
    ]


def _ticker_event_cache_key(
    ticker: str,
    *,
    as_of_date: str,
    history_period: str,
    history_interval: str,
    insider_limit: int,
    rsi_look_back_days: int,
    price_technical_lookback_days: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> str:
    return make_cache_key(
        _TICKER_EVENT_CACHE_NAMESPACE,
        *_ticker_event_cache_parts(
            ticker,
            as_of_date=as_of_date,
            history_period=history_period,
            history_interval=history_interval,
            insider_limit=insider_limit,
            rsi_look_back_days=rsi_look_back_days,
            price_technical_lookback_days=price_technical_lookback_days,
            start_date=start_date,
            end_date=end_date,
        ),
        version=_TICKER_EVENT_CACHE_VERSION,
    )


def _historical_bars(fetcher: Any, ticker: str, *, period: str, interval: str) -> List[Dict[str, Any]]:
    try:
        payload = fetcher.get_historical(ticker, period=period, interval=interval) or {}
    except Exception:
        return []
    rows = payload.get("data") or []
    return [row for row in rows if isinstance(row, dict)]


def _future_events(fetcher: Any, ticker: str) -> Any:
    try:
        getter = getattr(fetcher, "get_future_events", None)
        if getter is None:
            return {}
        return getter(ticker) or {}
    except Exception:
        return {}


def _insider_transactions(fetcher: Any, ticker: str, *, limit: int) -> Any:
    try:
        return fetcher.get_insider_transactions(ticker, limit=limit) or {}
    except Exception:
        return {}


def _rsi_map(fetcher: Any, ticker: str, *, as_of_date: str, look_back_days: int) -> Dict[str, float]:
    try:
        getter = getattr(fetcher, "get_indicators", None)
        if getter is None:
            return {}
        raw = getter(ticker, "rsi", as_of_date, look_back_days)
        return parse_rsi_indicator_data(raw)
    except Exception:
        return {}


def get_cached_ticker_event_summary(
    ticker: str,
    *,
    as_of_date: str,
    history_period: str = "1y",
    history_interval: str = "1d",
    insider_limit: int = 50,
    rsi_look_back_days: int = 60,
    price_technical_lookback_days: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[TickerEventSummary]:
    """Return a cached ticker event summary when available, without computing on miss."""

    payload = get_cached_raw(
        _ticker_event_cache_key(
            ticker,
            as_of_date=as_of_date,
            history_period=history_period,
            history_interval=history_interval,
            insider_limit=insider_limit,
            rsi_look_back_days=rsi_look_back_days,
            price_technical_lookback_days=price_technical_lookback_days,
            start_date=start_date,
            end_date=end_date,
        )
    )
    if payload is None:
        return None
    try:
        return TickerEventSummary.model_validate(payload)
    except Exception:
        return None


def warm_ticker_event_summary_async(
    fetcher: Any,
    ticker: str,
    *,
    as_of_date: str,
    history_period: str = "1y",
    history_interval: str = "1d",
    insider_limit: int = 50,
    rsi_look_back_days: int = 60,
    price_technical_lookback_days: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bool:
    """Warm the ticker event cache in the background when a summary is missing."""

    cache_key = _ticker_event_cache_key(
        ticker,
        as_of_date=as_of_date,
        history_period=history_period,
        history_interval=history_interval,
        insider_limit=insider_limit,
        rsi_look_back_days=rsi_look_back_days,
        price_technical_lookback_days=price_technical_lookback_days,
        start_date=start_date,
        end_date=end_date,
    )
    with _TICKER_EVENT_WARMING_LOCK:
        if cache_key in _TICKER_EVENT_WARMING_KEYS:
            return False
        _TICKER_EVENT_WARMING_KEYS.add(cache_key)

    def _warm() -> None:
        try:
            get_ticker_event_summary(
                fetcher,
                ticker,
                as_of_date=as_of_date,
                history_period=history_period,
                history_interval=history_interval,
                insider_limit=insider_limit,
                rsi_look_back_days=rsi_look_back_days,
                price_technical_lookback_days=price_technical_lookback_days,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            pass
        finally:
            with _TICKER_EVENT_WARMING_LOCK:
                _TICKER_EVENT_WARMING_KEYS.discard(cache_key)

    _TICKER_EVENT_WARMER.submit(_warm)
    return True


def get_ticker_event_summary(
    fetcher: Any,
    ticker: str,
    *,
    as_of_date: str,
    history_period: str = "1y",
    history_interval: str = "1d",
    insider_limit: int = 50,
    rsi_look_back_days: int = 60,
    price_technical_lookback_days: int = 10,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    bars: Optional[List[Dict[str, Any]]] = None,
    future_events: Any = None,
    insider_transactions: Any = None,
    rsi_data: Optional[Dict[str, float]] = None,
) -> TickerEventSummary:
    """
    Return a cached deterministic event snapshot for a ticker.

    Callers may provide preloaded inputs to avoid duplicate raw fetches on cache miss.
    """

    ticker_upper = ticker.upper()

    def _compute() -> Dict[str, Any]:
        resolved_bars = bars if bars is not None else _historical_bars(
            fetcher,
            ticker_upper,
            period=history_period,
            interval=history_interval,
        )
        if not resolved_bars:
            return TickerEventSummary(ticker=ticker_upper).model_dump(mode="json")

        resolved_future_events = future_events if future_events is not None else _future_events(fetcher, ticker_upper)
        resolved_insider = (
            insider_transactions
            if insider_transactions is not None
            else _insider_transactions(fetcher, ticker_upper, limit=insider_limit)
        )
        resolved_rsi = (
            rsi_data if rsi_data is not None else _rsi_map(fetcher, ticker_upper, as_of_date=as_of_date, look_back_days=rsi_look_back_days)
        )

        summary = extract_ticker_events(
            ticker_upper,
            bars=resolved_bars,
            as_of_date=as_of_date,
            future_events=resolved_future_events,
            insider_transactions=resolved_insider,
            rsi_data=resolved_rsi,
            price_technical_lookback_days=price_technical_lookback_days,
            start_date=start_date,
            end_date=end_date,
        )
        return summary.model_dump(mode="json")

    payload = get_or_set(
        _TICKER_EVENT_CACHE_NAMESPACE,
        parts=_ticker_event_cache_parts(
            ticker_upper,
            as_of_date=as_of_date,
            history_period=history_period,
            history_interval=history_interval,
            insider_limit=insider_limit,
            rsi_look_back_days=rsi_look_back_days,
            price_technical_lookback_days=price_technical_lookback_days,
            start_date=start_date,
            end_date=end_date,
        ),
        ttl_seconds=PROCESSING_CACHE_TTL_TICKER_EVENTS,
        fetch_fn=_compute,
        version=_TICKER_EVENT_CACHE_VERSION,
    )
    return TickerEventSummary.model_validate(payload)

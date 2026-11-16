"""Cached ticker event summaries built on top of normalized market data."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from .event import TickerEventSummary, extract_ticker_events, parse_rsi_indicator_data

# The cache lives in the backend (services.platform_cache / services.data_cache) and
# ai_engine may not import backend code. So the backend plugs its cache in through
# configure_event_cache() when backend.processing is imported (data_layer imports it,
# so every backend process and standalone script that sets up the gateway has it).
# Until then summaries are computed on every call and nothing is read from cache.
_cache: Dict[str, Any] = {}


def configure_event_cache(
    *,
    get_or_set: Callable[..., Any],
    get_cached_raw: Callable[[str], Any],
    make_cache_key: Callable[..., str],
    ttl_seconds: int,
) -> None:
    """Plug in the backend cache used by the ticker event summary functions."""
    _cache.update(
        get_or_set=get_or_set,
        get_cached_raw=get_cached_raw,
        make_cache_key=make_cache_key,
        ttl_seconds=ttl_seconds,
    )


def _make_cache_key(namespace: str, *parts: Any, version: str) -> str:
    maker = _cache.get("make_cache_key")
    if maker is not None:
        return maker(namespace, *parts, version=version)
    return ":".join([namespace, version, *(str(p) for p in parts)])


def _get_cached_raw(key: str) -> Any:
    getter = _cache.get("get_cached_raw")
    return getter(key) if getter is not None else None


def _get_or_set(namespace: str, *, parts: List[Any], ttl_seconds: Optional[int], fetch_fn: Callable[[], Any], version: str) -> Any:
    impl = _cache.get("get_or_set")
    if impl is None:
        return fetch_fn()
    return impl(namespace, parts=parts, ttl_seconds=ttl_seconds, fetch_fn=fetch_fn, version=version)

_TICKER_EVENT_CACHE_NAMESPACE = "processing:ticker_events"
# v2: summaries gained available/error, and v1 may hold 0.0 scores cached from failed loads.
_TICKER_EVENT_CACHE_VERSION = "v2"
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
    return _make_cache_key(
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


class _EventDataUnavailable(Exception):
    """Raised inside the cached compute so a failed load is never written to the cache.

    The backend cache stores whatever fetch_fn returns but does not store exceptions, so
    raising here (and turning it back into an "unavailable" summary outside _get_or_set)
    makes the next call retry the fetch instead of serving a cached empty result.
    """


def _unavailable_summary(ticker: str, error: str) -> TickerEventSummary:
    return TickerEventSummary(ticker=ticker, event_score=None, available=False, error=error)


def _historical_bars(fetcher: Any, ticker: str, *, period: str, interval: str) -> List[Dict[str, Any]]:
    # Errors are not swallowed here: a timeout used to become [] and then a cached
    # event_score of 0.0, which every caller (agents triaging tickers via
    # /api/data/events, the morning event monitor) read as "quiet ticker".
    try:
        payload = fetcher.get_historical(ticker, period=period, interval=interval) or {}
    except Exception as exc:
        raise _EventDataUnavailable(f"Price history could not be loaded: {type(exc).__name__}: {exc}") from exc
    rows = payload.get("data") or []
    bars = [row for row in rows if isinstance(row, dict)]
    if not bars:
        # A ticker that really exists always has some daily bars over the history
        # period, so no bars at all means the load failed, not that nothing happened.
        raise _EventDataUnavailable("Price history could not be loaded: no bars returned.")
    return bars


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

    payload = _get_cached_raw(
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

    When this function fetches the price history itself and it can't be loaded (the
    fetch raises or returns no bars), the result has ``event_score=None``,
    ``available=False`` and an ``error``, and it is not cached. The same holds when the
    caller passes preloaded ``bars`` that are empty.
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
            # The daily brief and stocks discovery load history in bulk and pass
            # `ohlcv_history.get(t) or []`, so a ticker whose bulk load failed arrives
            # here as an empty list. Scoring that 0.0 would present it as quiet.
            raise _EventDataUnavailable("Price history could not be loaded: no bars provided.")

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

    try:
        payload = _get_or_set(
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
            ttl_seconds=_cache.get("ttl_seconds"),
            fetch_fn=_compute,
            version=_TICKER_EVENT_CACHE_VERSION,
        )
    except _EventDataUnavailable as exc:
        return _unavailable_summary(ticker_upper, str(exc))
    return TickerEventSummary.model_validate(payload)

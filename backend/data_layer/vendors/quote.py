"""
Quote provider: fetches single/batch quotes via yfinance with yahooquery fallback.

All 3rd party access (yfinance, yahooquery) for quotes lives in this module.
"""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar

import pandas as pd
import yfinance as yf

from models.schemas import TickerQuote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helper for transient Yahoo Finance errors (HTTP 500 / 503)
# ---------------------------------------------------------------------------
_T = TypeVar("_T")

# Status codes that are transient and worth retrying
_TRANSIENT_HTTP_CODES = (500, 503)
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds; doubles each attempt (2, 4, 8)


def _is_transient_http_error(exc: Exception) -> bool:
    """Return True if the exception is a transient Yahoo HTTP 500 or 503."""
    msg = str(exc)
    return any(f"HTTP Error {code}" in msg for code in _TRANSIENT_HTTP_CODES)


def _yf_with_retry(fn: Callable[[], _T]) -> _T:
    """
    Call fn() and retry up to _RETRY_ATTEMPTS times on transient HTTP 500/503.
    On permanent errors (404, timeout, etc.) raises immediately.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            if _is_transient_http_error(exc):
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Yahoo transient error (attempt %d/%d): %s — retrying in %.0fs",
                    attempt, _RETRY_ATTEMPTS, exc, delay,
                )
                last_exc = exc
                time.sleep(delay)
            else:
                raise
    raise last_exc  # type: ignore[misc]

_RANGE_EXECUTOR: Optional[ThreadPoolExecutor] = None
_RANGE_BATCH_TIMEOUT_SEC = 28

MARKET_RANGE_PERIODS = {
    "1d": "5d",
    "1w": "5d",
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "ytd": "ytd",
}
MARKET_RANGE_OFFSETS = {
    "1d": 2,
    "1w": 6,
    "1mo": 22,
    "3mo": 64,
    "6mo": 126,
    "ytd": None,
}


def _get_range_executor() -> ThreadPoolExecutor:
    global _RANGE_EXECUTOR
    if _RANGE_EXECUTOR is None:
        _RANGE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="range_batch")
    return _RANGE_EXECUTOR


def _is_valid_price(price: float) -> bool:
    try:
        p = float(price)
        return p > 0 and not math.isnan(p) and not math.isinf(p)
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def _close_series_from_block(block: Any, *, prefer: str = "Close") -> Optional[Any]:
    if block is None or not hasattr(block, "columns"):
        if hasattr(block, "iloc") and hasattr(block, "dropna"):
            return block
        return None
    cols = block.columns
    if prefer in cols:
        return block[prefer]
    if "close" in cols:
        return block["close"]
    return None


def get_quote(ticker: str) -> Optional[Dict[str, Any]]:
    """Get current quote for a ticker. Uses yfinance with yahooquery fallback."""
    q = _get_quote_yfinance(ticker)
    if q is None:
        q = _get_quote_yahooquery(ticker)
    return q.model_dump() if q is not None else None


def get_quotes_batch(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get quotes for multiple tickers. Uses yfinance with yahooquery fallback for missing."""
    if not tickers:
        return {}
    tickers_upper = [t.upper() for t in tickers]
    results: Dict[str, Optional[TickerQuote]] = _get_quotes_batch_yfinance(tickers_upper)
    missing = [t for t in tickers_upper if results.get(t) is None]
    if missing:
        fallback = _get_quotes_batch_yahooquery(missing)
        for t, q in fallback.items():
            if q is not None:
                results[t] = q
    return {t: results[t].model_dump() if results.get(t) is not None else None for t in tickers_upper}


def get_quotes_batch_with_range(
    tickers: List[str],
    range_: Literal["1d", "1w", "1mo", "3mo", "6mo", "ytd"] = "1d",
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Get quotes with change over range. Uses yfinance with yahooquery fallback for missing."""
    if not tickers:
        return {}
    tickers_upper = [t.upper() for t in tickers]
    results: Dict[str, Optional[TickerQuote]] = _get_quotes_batch_with_range_yfinance(tickers_upper, range_)
    missing = [t for t in tickers_upper if results.get(t) is None]
    if missing:
        fallback = _get_quotes_batch_with_range_yahooquery(missing, range_)
        for t, q in fallback.items():
            if q is not None:
                results[t] = q
    return {t: results[t].model_dump() if results.get(t) is not None else None for t in tickers_upper}


def _get_quote_yfinance(ticker: str) -> Optional[TickerQuote]:
    ticker = ticker.upper()
    logger.info("Fetching quote from Yahoo (yfinance) for %s", ticker)
    try:
        ticker_obj = yf.Ticker(ticker)
        info = _yf_with_retry(lambda: ticker_obj.info)
        fast_info = ticker_obj.fast_info
        if info is None:
            info = {}
        if fast_info is None:
            fast_info = {}

        current_price = fast_info.get("lastPrice") or info.get("currentPrice") or info.get("regularMarketPrice")
        if current_price is None or not _is_valid_price(current_price):
            return None

        hist = ticker_obj.history(period="10d", interval="1d", auto_adjust=False, prepost=False)
        previous_close = None
        if hist is not None and not hist.empty and "Close" in hist.columns:
            close_series = hist["Close"].dropna()
            if len(close_series) >= 2:
                prev = float(close_series.iloc[-2])
                if _is_valid_price(prev):
                    previous_close = prev
        if previous_close is None:
            previous_close = fast_info.get("previousClose") or info.get("previousClose") or info.get("regularMarketPreviousClose")

        if previous_close and _is_valid_price(previous_close):
            daily_change = current_price - previous_close
            daily_change_percent = (daily_change / previous_close) * 100
        else:
            daily_change = 0.0
            daily_change_percent = 0.0

        bid_price = info.get("bid") or fast_info.get("bid")
        ask_price = info.get("ask") or fast_info.get("ask")
        volume = fast_info.get("volume") or info.get("volume") or info.get("regularMarketVolume")
        day_high = fast_info.get("dayHigh") or info.get("dayHigh") or info.get("regularMarketDayHigh")
        day_low = fast_info.get("dayLow") or info.get("dayLow") or info.get("regularMarketDayLow")
        fifty_two_week_high = info.get("fiftyTwoWeekHigh") or info.get("52WeekHigh")
        fifty_two_week_low = info.get("fiftyTwoWeekLow") or info.get("52WeekLow")
        market_state = (info.get("marketState") or "").upper()
        market_status = "OPEN" if market_state == "REGULAR" else "CLOSED" if market_state == "CLOSED" else "PRE_MARKET" if market_state == "PRE" else "AFTER_HOURS" if market_state == "POST" else "UNKNOWN"
        currency_raw = info.get("currency") or fast_info.get("currency")
        currency = currency_raw if isinstance(currency_raw, str) else None

        return TickerQuote(
            ticker=ticker,
            current_price=round(float(current_price), 2),
            daily_change=round(float(daily_change), 2),
            daily_change_percent=round(float(daily_change_percent), 2),
            bid_price=round(float(bid_price), 2) if bid_price else None,
            ask_price=round(float(ask_price), 2) if ask_price else None,
            bid_size=int(info.get("bidSize")) if info.get("bidSize") else None,
            ask_size=int(info.get("askSize")) if info.get("askSize") else None,
            volume=int(volume) if volume else None,
            previous_close=round(float(previous_close), 2) if previous_close else None,
            day_high=round(float(day_high), 2) if day_high else None,
            day_low=round(float(day_low), 2) if day_low else None,
            fifty_two_week_high=round(float(fifty_two_week_high), 2) if fifty_two_week_high else None,
            fifty_two_week_low=round(float(fifty_two_week_low), 2) if fifty_two_week_low else None,
            market_status=market_status,
            last_update_time=datetime.now(),
            currency=currency,
        )
    except Exception as e:
        logger.warning("yfinance quote failed for %s: %s", ticker, e)
        return None


def _get_quote_yahooquery(ticker: str) -> Optional[TickerQuote]:
    try:
        from yahooquery import Ticker as YahooQueryTicker
    except ImportError:
        return None
    ticker = ticker.upper()
    logger.info("Fetching quote from Yahoo (yahooquery) for %s", ticker)
    try:
        tq = YahooQueryTicker(ticker)
        raw = tq.get_modules("price summaryDetail")
        if not isinstance(raw, dict):
            raw = {}
        per = raw.get(ticker) or raw.get(ticker.lower())
        if not isinstance(per, dict):
            df = tq.history(period="5d", interval="1d")
            if df is None or df.empty or "close" not in getattr(df, "columns", []):
                return None
            close_series = df["close"].dropna()
            if len(close_series) < 1:
                return None
            current = _safe_float(close_series.iloc[-1])
            if current is None or not _is_valid_price(current):
                return None
            prev = _safe_float(close_series.iloc[-2]) if len(close_series) >= 2 else current
            if prev is None or not _is_valid_price(prev):
                prev = current
            change = current - prev
            change_pct = (change / prev * 100.0) if prev and prev > 0 else 0.0
            vol = _safe_int(df["volume"].iloc[-1]) if "volume" in df.columns and len(df) else None
            return TickerQuote(
                ticker=ticker,
                current_price=round(current, 2),
                daily_change=round(change, 2),
                daily_change_percent=round(change_pct, 2),
                bid_price=None,
                ask_price=None,
                bid_size=None,
                ask_size=None,
                volume=vol,
                previous_close=round(prev, 2),
                day_high=None,
                day_low=None,
                fifty_two_week_high=None,
                fifty_two_week_low=None,
                market_status="UNKNOWN",
                last_update_time=datetime.now(),
                currency=None,
            )
        price = per.get("price") if isinstance(per.get("price"), dict) else {}
        summary = per.get("summaryDetail") if isinstance(per.get("summaryDetail"), dict) else {}
        return _ticker_quote_from_yahooquery(ticker, price, summary)
    except Exception:
        return None


def _yq_coerce(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v):
        return float(v)
    if isinstance(v, dict) and "raw" in v:
        r = v.get("raw")
        if r is not None and isinstance(r, (int, float)):
            return float(r)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ticker_quote_from_yahooquery(ticker: str, price: Dict, summary: Dict) -> Optional[TickerQuote]:
    if not price:
        return None
    current_price = _yq_coerce(price.get("regularMarketPrice") or price.get("regularMarketPreviousClose"))
    if current_price is None or not _is_valid_price(current_price):
        return None
    prev_close = _yq_coerce(price.get("regularMarketPreviousClose") or summary.get("previousClose"))
    if prev_close is None or not _is_valid_price(prev_close):
        prev_close = current_price
    change_pct_raw = _yq_coerce(price.get("regularMarketChangePercent"))
    if change_pct_raw is not None:
        change_pct = change_pct_raw * 100.0 if abs(change_pct_raw) <= 1.5 else change_pct_raw
        daily_change = (change_pct / 100.0) * prev_close if prev_close else 0.0
    else:
        daily_change = current_price - prev_close
        change_pct = (daily_change / prev_close * 100.0) if prev_close and prev_close > 0 else 0.0
    currency = price.get("currency") or summary.get("currency")
    currency = currency if isinstance(currency, str) else None
    state = (price.get("marketState") or "")
    if isinstance(state, dict):
        state = state.get("raw") or state.get("fmt") or ""
    s = str(state).upper()
    market_status = "OPEN" if s == "REGULAR" else "CLOSED" if s == "CLOSED" else "PRE_MARKET" if s == "PRE" else "AFTER_HOURS" if s == "POST" else "UNKNOWN"
    return TickerQuote(
        ticker=ticker.upper(),
        current_price=round(current_price, 2),
        daily_change=round(daily_change, 2),
        daily_change_percent=round(change_pct, 2),
        bid_price=_yq_coerce(price.get("bid")),
        ask_price=_yq_coerce(price.get("ask")),
        bid_size=None,
        ask_size=None,
        volume=_safe_int(_yq_coerce(price.get("regularMarketVolume") or summary.get("volume"))),
        previous_close=round(prev_close, 2),
        day_high=_yq_coerce(price.get("regularMarketDayHigh")),
        day_low=_yq_coerce(price.get("regularMarketDayLow")),
        fifty_two_week_high=_yq_coerce(summary.get("fiftyTwoWeekHigh") or price.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_yq_coerce(summary.get("fiftyTwoWeekLow") or price.get("fiftyTwoWeekLow")),
        market_status=market_status,
        last_update_time=datetime.now(),
        currency=currency,
    )


def _get_quotes_batch_yfinance(tickers: List[str]) -> Dict[str, Optional[TickerQuote]]:
    if not tickers:
        return {}
    tickers = [t.upper() for t in tickers]
    results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
    try:
        data = _yf_with_retry(lambda: yf.download(
            tickers,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False,
        ))
        if data is None or data.empty or not hasattr(data, "columns"):
            return results
        for t in tickers:
            try:
                if len(tickers) == 1:
                    close_col = _close_series_from_block(data) if not isinstance(data.columns, pd.MultiIndex) else _close_series_from_block(data[t]) if t in data.columns.get_level_values(0) else None
                else:
                    close_col = _close_series_from_block(data[t]) if t in data.columns.get_level_values(0) else None
                if close_col is None:
                    continue
                valid = close_col.dropna()
                if len(valid) < 1:
                    continue
                current = _safe_float(valid.iloc[-1])
                if current is None or not _is_valid_price(current):
                    continue
                prev = _safe_float(valid.iloc[-2]) if len(valid) >= 2 else current
                if prev is None or not _is_valid_price(prev):
                    prev = current
                daily_change = current - prev
                daily_change_percent = (daily_change / prev * 100) if prev and prev > 0 else 0.0
                vol = None
                if len(tickers) == 1:
                    vol = _safe_int(data["Volume"].iloc[-1]) if "Volume" in data.columns else None
                elif (t, "Volume") in data.columns:
                    vol = _safe_int(data[(t, "Volume")].iloc[-1])
                results[t] = TickerQuote(
                    ticker=t,
                    current_price=round(current, 2),
                    daily_change=round(daily_change, 2),
                    daily_change_percent=round(daily_change_percent, 2),
                    bid_price=None,
                    ask_price=None,
                    bid_size=None,
                    ask_size=None,
                    volume=vol,
                    previous_close=round(prev, 2) if prev else None,
                    day_high=None,
                    day_low=None,
                    fifty_two_week_high=None,
                    fifty_two_week_low=None,
                    market_status="UNKNOWN",
                    last_update_time=datetime.now(),
                    currency=None,
                )
            except Exception as e:
                logger.warning("Parse batch quote failed for %s: %s", t, e)
    except Exception as e:
        logger.warning("Batch quote fetch failed: %s", e)
    return results


def _get_quotes_batch_yahooquery(tickers: List[str]) -> Dict[str, Optional[TickerQuote]]:
    if not tickers:
        return {}
    results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
    try:
        from yahooquery import Ticker as YahooQueryTicker
    except ImportError:
        return results
    for i in range(0, len(tickers), 25):
        chunk = [t.upper() for t in tickers[i : i + 25]]
        try:
            tq = YahooQueryTicker(chunk)
            raw = tq.get_modules("price summaryDetail")
            if not isinstance(raw, dict):
                continue
            for t in chunk:
                per = raw.get(t) or raw.get(t.lower())
                if not isinstance(per, dict):
                    continue
                price = per.get("price") if isinstance(per.get("price"), dict) else {}
                summary = per.get("summaryDetail") if isinstance(per.get("summaryDetail"), dict) else {}
                q = _ticker_quote_from_yahooquery(t, price, summary)
                if q is not None:
                    results[t] = q
        except Exception:
            continue
    for t in tickers:
        if results.get(t) is None:
            q = _get_quote_yahooquery(t)
            if q is not None:
                results[t] = q
    return results


def _get_quotes_batch_with_range_yfinance(
    tickers: List[str],
    range_: Literal["1d", "1w", "1mo", "3mo", "6mo", "ytd"],
) -> Dict[str, Optional[TickerQuote]]:
    if not tickers or range_ == "1d":
        return _get_quotes_batch_yfinance(tickers)
    tickers = [t.upper() for t in tickers]
    results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
    period = MARKET_RANGE_PERIODS.get(range_, "1mo")
    offset = MARKET_RANGE_OFFSETS.get(range_)
    executor = _get_range_executor()

    def _download_chunk(chunk_tickers: List[str], period_str: str) -> Optional[pd.DataFrame]:
        out = _yf_with_retry(lambda: yf.download(
            chunk_tickers,
            period=period_str,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False,
        ))
        return out if out is not None and not (isinstance(out, pd.DataFrame) and out.empty) else None

    for i in range(0, len(tickers), 25):
        chunk = tickers[i : i + 25]
        try:
            future = executor.submit(_download_chunk, chunk, period)
            data = future.result(timeout=_RANGE_BATCH_TIMEOUT_SEC)
            if data is None or not hasattr(data, "columns"):
                continue
            for t in chunk:
                try:
                    if len(chunk) == 1:
                        close_series = data["Close"] if "Close" in data.columns else data.get("close")
                    else:
                        if t not in data.columns.get_level_values(0):
                            continue
                        t_block = data[t]
                        close_series = t_block["Close"] if "Close" in t_block.columns else t_block.get("close")
                    if close_series is None:
                        continue
                    valid = close_series.dropna()
                    if len(valid) < 1:
                        continue
                    current = _safe_float(valid.iloc[-1])
                    if current is None or not _is_valid_price(current):
                        continue
                    if offset is not None and len(valid) >= 2:
                        prev = _safe_float(valid.iloc[-offset]) if len(valid) >= offset else _safe_float(valid.iloc[0])
                    elif len(valid) >= 2:
                        yr = datetime.now().year
                        prev = None
                        for j in range(len(valid)):
                            idx = valid.index[j]
                            if hasattr(idx, "year") and idx.year == yr:
                                prev = _safe_float(valid.iloc[j])
                                break
                        prev = prev or _safe_float(valid.iloc[0])
                    else:
                        prev = current
                    if prev is None or not _is_valid_price(prev) or prev <= 0:
                        prev = current
                    change = current - prev
                    change_pct = (change / prev * 100.0) if prev and prev > 0 else 0.0
                    vol_series = None
                    if len(chunk) == 1 and "Volume" in data.columns:
                        vol_series = data["Volume"]
                    elif len(chunk) > 1 and (t, "Volume") in data.columns:
                        vol_series = data[(t, "Volume")]
                    vol = _safe_int(vol_series.iloc[-1]) if vol_series is not None else None
                    results[t] = TickerQuote(
                        ticker=t,
                        current_price=round(current, 2),
                        daily_change=round(change, 2),
                        daily_change_percent=round(change_pct, 2),
                        bid_price=None,
                        ask_price=None,
                        bid_size=None,
                        ask_size=None,
                        volume=vol,
                        previous_close=round(prev, 2) if prev else None,
                        day_high=None,
                        day_low=None,
                        fifty_two_week_high=None,
                        fifty_two_week_low=None,
                        market_status="UNKNOWN",
                        last_update_time=datetime.now(),
                        currency=None,
                    )
                except Exception as e:
                    logger.warning("Range quote parse failed for %s: %s", t, e)
        except FuturesTimeoutError:
            logger.warning("Range batch timed out")
        except Exception as e:
            logger.warning("Range batch failed: %s", e)
    return results


def _get_quotes_batch_with_range_yahooquery(
    tickers: List[str],
    range_: Literal["1d", "1w", "1mo", "3mo", "6mo", "ytd"],
) -> Dict[str, Optional[TickerQuote]]:
    if not tickers:
        return {}
    try:
        from yahooquery import Ticker as YahooQueryTicker
    except ImportError:
        return {t: None for t in tickers}
    period = MARKET_RANGE_PERIODS.get(range_, "1mo")
    offset = MARKET_RANGE_OFFSETS.get(range_)
    results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
    for i in range(0, len(tickers), 25):
        chunk = [t.upper() for t in tickers[i : i + 25]]
        try:
            tq = YahooQueryTicker(chunk)
            df = tq.history(period=period, interval="1d")
            if df is None or df.empty:
                continue
            has_multi = hasattr(df.index, "levels") and len(df.index.names) >= 2
            for t in chunk:
                try:
                    if has_multi:
                        sym_to_key = {str(s).upper(): s for s in df.index.get_level_values(0).unique()}
                        key = sym_to_key.get(t) or sym_to_key.get(t.upper())
                        if key is None:
                            continue
                        sub = df.xs(key, level=0)
                        close_series = sub["close"].dropna() if "close" in sub.columns else None
                    else:
                        close_series = df["close"].dropna() if "close" in df.columns else None
                    if close_series is None or len(close_series) < 1:
                        continue
                    current = _safe_float(close_series.iloc[-1])
                    if current is None or not _is_valid_price(current):
                        continue
                    if offset is not None and len(close_series) >= 2:
                        prev = _safe_float(close_series.iloc[-offset]) if len(close_series) >= offset else _safe_float(close_series.iloc[0])
                    elif len(close_series) >= 2:
                        yr = datetime.now().year
                        prev = None
                        for j in range(len(close_series)):
                            idx = close_series.index[j]
                            if hasattr(idx, "year") and idx.year == yr:
                                prev = _safe_float(close_series.iloc[j])
                                break
                        prev = prev or _safe_float(close_series.iloc[0])
                    else:
                        prev = current
                    if prev is None or not _is_valid_price(prev) or prev <= 0:
                        prev = current
                    change = current - prev
                    change_pct = (change / prev * 100.0) if prev and prev > 0 else 0.0
                    vol = None
                    if has_multi and "volume" in sub.columns:
                        vol = _safe_int(sub["volume"].iloc[-1])
                    elif not has_multi and "volume" in df.columns:
                        vol = _safe_int(df["volume"].iloc[-1])
                    results[t] = TickerQuote(
                        ticker=t,
                        current_price=round(current, 2),
                        daily_change=round(change, 2),
                        daily_change_percent=round(change_pct, 2),
                        bid_price=None,
                        ask_price=None,
                        bid_size=None,
                        ask_size=None,
                        volume=vol,
                        previous_close=round(prev, 2) if prev else None,
                        day_high=None,
                        day_low=None,
                        fifty_two_week_high=None,
                        fifty_two_week_low=None,
                        market_status="UNKNOWN",
                        last_update_time=datetime.now(),
                        currency=None,
                    )
                except Exception:
                    pass
        except Exception:
            continue
    return results

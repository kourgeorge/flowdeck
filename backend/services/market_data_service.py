"""Service to fetch real-time market data using yfinance, with yahooquery fallback when Yahoo returns 401."""

import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import yfinance as yf
import pandas as pd
from typing import List, Optional, Dict, Literal, Any
from datetime import datetime
from models.schemas import TickerQuote

# Per-batch timeout for range downloads (yf.download can hang on Yahoo for 1w/regions).
_RANGE_BATCH_TIMEOUT_SEC = 28
_RANGE_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _get_range_executor() -> ThreadPoolExecutor:
    global _RANGE_EXECUTOR
    if _RANGE_EXECUTOR is None:
        _RANGE_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="range_batch")
    return _RANGE_EXECUTOR

MARKET_RANGE_PERIODS = {
    "1d": "5d",
    "1w": "5d",   # 5d gives ~5 bars; if fewer than offset 6 we use first row (slightly shorter window, smaller payload)
    "1mo": "1mo",
    "3mo": "3mo",
    "6mo": "6mo",
    "ytd": "ytd",
}
# Index offset from last close: -1 is current, -2 is prev day. For 1w: 5 sessions back = -6, 1mo: -22, 3mo: -64, 6mo: ~126
MARKET_RANGE_OFFSETS = {
    "1d": 2,  # prev close
    "1w": 6,  # 5 trading days back
    "1mo": 22,  # ~21 trading days
    "3mo": 64,  # ~63 trading days
    "6mo": 126,  # ~6 months of trading days
    "ytd": None,  # use first row of current year
}


def _is_valid_price(price: float) -> bool:
    """Return True if price is a valid positive number (not NaN, not zero or negative)."""
    try:
        p = float(price)
        return p > 0 and not math.isnan(p) and not math.isinf(p)
    except (TypeError, ValueError):
        return False


def _safe_float(value, default: Optional[float] = None) -> Optional[float]:
    """Convert value to float, returning default if NaN/Inf/None/error."""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_int(value) -> Optional[int]:
    """Convert value to int, returning None if NaN/Inf/None/error."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


class MarketDataService:
    """Service for fetching real-time market data."""

    @staticmethod
    def _get_previous_close_from_history(ticker_obj: yf.Ticker) -> Optional[float]:
        """
        Resolve previous close from Yahoo daily history.
        Using the prior completed session close is more reliable than fast_info/info
        around corporate actions and inconsistent quote fields.
        """
        try:
            hist = ticker_obj.history(
                period="10d",
                interval="1d",
                auto_adjust=False,
                prepost=False,
            )
            if hist.empty or "Close" not in hist.columns:
                return None
            close_series = hist["Close"].dropna()
            if len(close_series) < 2:
                return None
            prev_close = float(close_series.iloc[-2])
            return prev_close if _is_valid_price(prev_close) else None
        except Exception:
            return None
    
    @staticmethod
    def _get_market_status(ticker_info: dict) -> str:
        """Determine market status from ticker info."""
        market_state = ticker_info.get('marketState', '').upper()
        
        if market_state == 'REGULAR':
            return 'OPEN'
        elif market_state == 'CLOSED':
            return 'CLOSED'
        elif market_state == 'PRE':
            return 'PRE_MARKET'
        elif market_state == 'POST':
            return 'AFTER_HOURS'
        else:
            return 'UNKNOWN'
    
    @staticmethod
    def get_current_quote(ticker: str) -> Optional[TickerQuote]:
        """Get current market quote for a ticker."""
        try:
            ticker_obj = yf.Ticker(ticker.upper())
            info = ticker_obj.info
            fast_info = ticker_obj.fast_info
            # Yahoo often returns 401 (Invalid Crumb / rate limit); yfinance then gives None for info/fast_info
            if info is None:
                info = {}
            if fast_info is None:
                fast_info = {}
            
            # Get current price
            current_price = fast_info.get('lastPrice') or info.get('currentPrice') or info.get('regularMarketPrice')
            if current_price is None or not _is_valid_price(current_price):
                return MarketDataService.get_current_quote_yahooquery(ticker)
            
            # Prefer previous close from daily history to match Yahoo's displayed change basis.
            previous_close = MarketDataService._get_previous_close_from_history(ticker_obj)
            if previous_close is None:
                previous_close = (
                    fast_info.get('previousClose')
                    or info.get('previousClose')
                    or info.get('regularMarketPreviousClose')
                )
            
            # Calculate change
            if previous_close and _is_valid_price(previous_close):
                daily_change = current_price - previous_close
                daily_change_percent = (daily_change / previous_close) * 100
            else:
                daily_change = 0.0
                daily_change_percent = 0.0
            
            # Get bid/ask
            bid_price = info.get('bid') or fast_info.get('bid')
            ask_price = info.get('ask') or fast_info.get('ask')
            bid_size = info.get('bidSize')
            ask_size = info.get('askSize')
            
            # Get volume
            volume = fast_info.get('volume') or info.get('volume') or info.get('regularMarketVolume')
            
            # Get day high/low
            day_high = fast_info.get('dayHigh') or info.get('dayHigh') or info.get('regularMarketDayHigh')
            day_low = fast_info.get('dayLow') or info.get('dayLow') or info.get('regularMarketDayLow')
            
            # Get 52-week range
            fifty_two_week_high = info.get('fiftyTwoWeekHigh') or info.get('52WeekHigh')
            fifty_two_week_low = info.get('fiftyTwoWeekLow') or info.get('52WeekLow')
            
            # Get market status
            market_status = MarketDataService._get_market_status(info)
            
            return TickerQuote(
                ticker=ticker.upper(),
                current_price=round(float(current_price), 2),
                daily_change=round(float(daily_change), 2),
                daily_change_percent=round(float(daily_change_percent), 2),
                bid_price=round(float(bid_price), 2) if bid_price else None,
                ask_price=round(float(ask_price), 2) if ask_price else None,
                bid_size=int(bid_size) if bid_size else None,
                ask_size=int(ask_size) if ask_size else None,
                volume=int(volume) if volume else None,
                previous_close=round(float(previous_close), 2) if previous_close else None,
                day_high=round(float(day_high), 2) if day_high else None,
                day_low=round(float(day_low), 2) if day_low else None,
                fifty_two_week_high=round(float(fifty_two_week_high), 2) if fifty_two_week_high else None,
                fifty_two_week_low=round(float(fifty_two_week_low), 2) if fifty_two_week_low else None,
                market_status=market_status,
                last_update_time=datetime.now()
            )
        except Exception as e:
            print(f"Error fetching quote for {ticker}: {e}")
            return MarketDataService.get_current_quote_yahooquery(ticker)
    
    @staticmethod
    def get_multiple_quotes(tickers: List[str]) -> Dict[str, Optional[TickerQuote]]:
        """Get quotes for multiple tickers (sequential fallback). Prefer get_multiple_quotes_batch for speed."""
        return MarketDataService.get_multiple_quotes_batch(tickers)

    @staticmethod
    def get_multiple_quotes_batch(tickers: List[str]) -> Dict[str, Optional[TickerQuote]]:
        """Fetch quotes for multiple tickers in one batch request via yf.download.

        daily_change_percent is (last close - previous close) / previous close * 100.
        - Market open: last close is today's bar (updated by Yahoo); previous close is prior session. Valid.
        - Market closed: last = session close, previous = prior session close. Valid.
        - Continuous (crypto): daily bars still give last vs previous day close. Valid.
        """
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
        try:
            # One network request for all tickers (period=5d gives us current + previous close)
            data = yf.download(
                tickers,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                prepost=False,
                threads=True,
                progress=False,
            )
            # Yahoo 401/rate limit can make yfinance return None or a DataFrame with no usable columns
            if data is None or data.empty:
                return results
            if not hasattr(data, "columns") or data.columns is None:
                return results
            # Handle single-ticker vs multi-ticker DataFrame shape
            if len(tickers) == 1:
                # Single ticker: columns are flat (Open, High, Low, Close, ...)
                t = tickers[0]
                if isinstance(data.columns, pd.MultiIndex) and t in data.columns.get_level_values(0):
                    t_data = data[t]
                    close_series = t_data["Close"] if "Close" in t_data.columns else None
                    volume_series = t_data["Volume"] if "Volume" in t_data.columns else None
                    high_series = t_data["High"] if "High" in t_data.columns else None
                    low_series = t_data["Low"] if "Low" in t_data.columns else None
                else:
                    close_series = data["Close"] if "Close" in data.columns else None
                    volume_series = data["Volume"] if "Volume" in data.columns else None
                    high_series = data["High"] if "High" in data.columns else None
                    low_series = data["Low"] if "Low" in data.columns else None

                if close_series is not None and len(close_series) >= 1:
                    # Use only valid closes so we get a real previous close when the raw series has NaNs (e.g. multi-ticker date alignment)
                    valid_closes = close_series.dropna()
                    if len(valid_closes) < 1:
                        pass
                    else:
                        current = _safe_float(valid_closes.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            pass
                        else:
                            prev = _safe_float(valid_closes.iloc[-2]) if len(valid_closes) >= 2 else None
                            if prev is None or not _is_valid_price(prev):
                                prev = current
                            daily_change = current - prev
                            daily_change_percent = (daily_change / prev * 100) if prev and prev > 0 else 0.0
                            results[t] = TickerQuote(
                                ticker=t,
                                current_price=round(current, 2),
                                daily_change=round(daily_change, 2),
                                daily_change_percent=round(daily_change_percent, 2),
                                bid_price=None,
                                ask_price=None,
                                bid_size=None,
                                ask_size=None,
                                volume=_safe_int(volume_series.iloc[-1]) if volume_series is not None else None,
                                previous_close=round(prev, 2) if prev is not None else None,
                                day_high=_safe_float(high_series.iloc[-1]) if high_series is not None else None,
                                day_low=_safe_float(low_series.iloc[-1]) if low_series is not None else None,
                                fifty_two_week_high=None,
                                fifty_two_week_low=None,
                                market_status="UNKNOWN",
                                last_update_time=datetime.now(),
                            )
                elif close_series is not None and len(close_series) == 1:
                    valid_closes = close_series.dropna()
                    current = _safe_float(valid_closes.iloc[-1]) if len(valid_closes) >= 1 else None
                    if current is not None and _is_valid_price(current):
                        results[t] = TickerQuote(
                            ticker=t,
                            current_price=round(current, 2),
                            daily_change=0.0,
                            daily_change_percent=0.0,
                            bid_price=None,
                            ask_price=None,
                            bid_size=None,
                            ask_size=None,
                            volume=_safe_int(volume_series.iloc[-1]) if volume_series is not None else None,
                            previous_close=round(current, 2),
                            day_high=_safe_float(high_series.iloc[-1]) if high_series is not None else None,
                            day_low=_safe_float(low_series.iloc[-1]) if low_series is not None else None,
                            fifty_two_week_high=None,
                            fifty_two_week_low=None,
                            market_status="UNKNOWN",
                            last_update_time=datetime.now(),
                        )
            else:
                # Multi-ticker: columns are MultiIndex (ticker, OHLCV) or (Ticker, Price)
                for t in tickers:
                    try:
                        if t in data.columns.get_level_values(0):
                            close_col = data[t]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"][t]
                        else:
                            close_col = data["Close"].get(t) if hasattr(data["Close"], "get") else None
                        if close_col is None:
                            continue
                        close_series = close_col if hasattr(close_col, "iloc") else close_col
                        valid_closes = close_series.dropna()
                        if len(valid_closes) < 1:
                            continue
                        current = _safe_float(valid_closes.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            continue
                        if len(valid_closes) >= 2:
                            prev = _safe_float(valid_closes.iloc[-2])
                            if prev is None or not _is_valid_price(prev):
                                prev = current
                        else:
                            prev = current
                        daily_change = current - prev
                        daily_change_percent = (daily_change / prev * 100) if prev and prev > 0 else 0.0
                        vol = None
                        high = low = None
                        if isinstance(data.columns, pd.MultiIndex):
                            if (t, "Volume") in data.columns:
                                vol = _safe_int(data[(t, "Volume")].iloc[-1])
                            if (t, "High") in data.columns:
                                high = _safe_float(data[(t, "High")].iloc[-1])
                            if (t, "Low") in data.columns:
                                low = _safe_float(data[(t, "Low")].iloc[-1])
                        else:
                            if "Volume" in data.columns and t in data["Volume"].columns:
                                vol = _safe_int(data["Volume"][t].iloc[-1])
                            if "High" in data.columns and t in data["High"].columns:
                                high = _safe_float(data["High"][t].iloc[-1])
                            if "Low" in data.columns and t in data["Low"].columns:
                                low = _safe_float(data["Low"][t].iloc[-1])
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
                            previous_close=round(prev, 2) if prev is not None else None,
                            day_high=round(high, 2) if high is not None else None,
                            day_low=round(low, 2) if low is not None else None,
                            fifty_two_week_high=None,
                            fifty_two_week_low=None,
                            market_status="UNKNOWN",
                            last_update_time=datetime.now(),
                        )
                    except Exception as e:
                        print(f"Warning: Failed to parse batch quote for {t}: {e}")
        except Exception as e:
            print(f"Warning: Batch quote fetch failed: {e}")
        # Fallback: yahooquery for tickers that got no data (e.g. yfinance 401)
        missing = [t for t in tickers if results[t] is None]
        if missing:
            fallback = MarketDataService._get_multiple_quotes_batch_yahooquery(missing)
            for t, q in fallback.items():
                if q is not None:
                    results[t] = q
        return results

    @staticmethod
    def get_multiple_quotes_batch_with_range(
        tickers: List[str],
        range_: Literal["1d", "1w", "1mo", "3mo", "6mo", "ytd"] = "1d",
    ) -> Dict[str, Optional[TickerQuote]]:
        """Fetch quotes with change over the specified range (1d, 1w, 1mo, 3mo, ytd).
        For 1d uses previous close; for 1w/1mo/3mo uses close N sessions ago; for ytd uses year-start close.
        Downloads in batches to avoid empty responses from Yahoo when requesting many tickers at once."""
        if not tickers:
            return {}
        if range_ == "1d":
            return MarketDataService.get_multiple_quotes_batch(tickers)

        tickers = [t.upper() for t in tickers]
        results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
        period = MARKET_RANGE_PERIODS.get(range_, "1mo")
        offset = MARKET_RANGE_OFFSETS.get(range_)

        def _download_chunk(chunk_tickers: List[str], period_str: str) -> Optional[pd.DataFrame]:
            out = yf.download(
                chunk_tickers,
                period=period_str,
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                prepost=False,
                threads=True,
                progress=False,
            )
            return out if out is not None and not (isinstance(out, pd.DataFrame) and out.empty) else None

        batch_size = 25
        executor = _get_range_executor()
        for i in range(0, len(tickers), batch_size):
            chunk = tickers[i : i + batch_size]
            try:
                future = executor.submit(_download_chunk, chunk, period)
                data = future.result(timeout=_RANGE_BATCH_TIMEOUT_SEC)
                if data is None or not hasattr(data, "columns") or data.columns is None:
                    continue

                def get_close_series(data: pd.DataFrame, chunk_tickers: List[str], t: str):
                    if len(chunk_tickers) == 1:
                        tc = chunk_tickers[0]
                        if isinstance(data.columns, pd.MultiIndex) and tc in data.columns.get_level_values(0):
                            return data[tc]["Close"] if "Close" in data[tc].columns else None
                        return data["Close"] if "Close" in data.columns else None
                    if not isinstance(data.columns, pd.MultiIndex):
                        return None
                    if t in data.columns.get_level_values(0):
                        return data[t]["Close"] if "Close" in data[t].columns else None
                    if t in data.columns.get_level_values(1) and "Close" in data.columns.get_level_values(0):
                        return data["Close"].get(t)
                    return None

                def get_volume_series(data: pd.DataFrame, chunk_tickers: List[str], t: str):
                    if len(chunk_tickers) == 1:
                        tc = chunk_tickers[0]
                        if isinstance(data.columns, pd.MultiIndex) and tc in data.columns.get_level_values(0):
                            return data[tc]["Volume"] if "Volume" in data[tc].columns else None
                        return data["Volume"] if "Volume" in data.columns else None
                    if not isinstance(data.columns, pd.MultiIndex):
                        return None
                    if (t, "Volume") in data.columns:
                        return data[(t, "Volume")]
                    if t in data.columns.get_level_values(0) and "Volume" in data[t].columns:
                        return data[t]["Volume"]
                    if t in data.columns.get_level_values(1) and "Volume" in data.columns.get_level_values(0):
                        return data["Volume"].get(t)
                    return None

                for t in chunk:
                    try:
                        close_series = get_close_series(data, chunk, t)
                        if close_series is None:
                            continue
                        valid = close_series.dropna()
                        if len(valid) < 1:
                            continue
                        current = _safe_float(valid.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            continue

                        if len(valid) >= 2:
                            if offset is not None:
                                if len(valid) < offset:
                                    prev = _safe_float(valid.iloc[0])
                                else:
                                    prev = _safe_float(valid.iloc[-offset])
                            else:
                                today = datetime.now()
                                yr = today.year
                                prev = None
                                for j in range(len(valid)):
                                    idx = valid.index[j]
                                    if hasattr(idx, "year") and idx.year == yr:
                                        prev = _safe_float(valid.iloc[j])
                                        break
                                if prev is None:
                                    prev = _safe_float(valid.iloc[0])
                        else:
                            prev = current
                        if prev is None or not _is_valid_price(prev) or prev <= 0:
                            prev = current
                        change = current - prev
                        change_pct = (change / prev * 100) if prev and prev > 0 else 0.0

                        vol_series = get_volume_series(data, chunk, t)
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
                        )
                    except Exception as e:
                        print(f"Warning: Failed to parse range quote for {t}: {e}")
            except FuturesTimeoutError:
                print(f"Warning: Batch range quote fetch timed out for chunk (>{_RANGE_BATCH_TIMEOUT_SEC}s), skipping")
            except Exception as e:
                print(f"Warning: Batch range quote fetch failed for chunk: {e}")

        # Retry tickers that got no data (Yahoo often returns incomplete data in large batches).
        # Use a longer period for single-ticker fetch to get more rows (e.g. 3mo for 1w/1mo range).
        missing = [t for t in tickers if results[t] is None]
        if not missing:
            return results
        retry_period = "3mo" if period in ("1mo", "5d") else period
        for t in missing:
            try:
                future = executor.submit(
                    _download_chunk,
                    [t],
                    retry_period,
                )
                data = future.result(timeout=_RANGE_BATCH_TIMEOUT_SEC)
                if data is None or not hasattr(data, "columns") or data.columns is None:
                    continue
                # Single-ticker download: flat columns or MultiIndex (ticker, OHLCV)
                if isinstance(data.columns, pd.MultiIndex) and t in data.columns.get_level_values(0):
                    close_series = data[t]["Close"] if "Close" in data[t].columns else None
                    vol_series = data[t]["Volume"] if "Volume" in data[t].columns else None
                else:
                    close_series = data["Close"] if "Close" in data.columns else None
                    vol_series = data["Volume"] if "Volume" in data.columns else None
                if close_series is None:
                    continue
                valid = close_series.dropna()
                if len(valid) < 1:
                    continue
                current = _safe_float(valid.iloc[-1])
                if current is None or not _is_valid_price(current):
                    continue
                if len(valid) >= 2:
                    if offset is not None:
                        prev = _safe_float(valid.iloc[-offset]) if len(valid) >= offset else _safe_float(valid.iloc[0])
                    else:
                        today = datetime.now()
                        yr = today.year
                        prev = None
                        for j in range(len(valid)):
                            idx = valid.index[j]
                            if hasattr(idx, "year") and idx.year == yr:
                                prev = _safe_float(valid.iloc[j])
                                break
                        if prev is None:
                            prev = _safe_float(valid.iloc[0])
                else:
                    prev = current
                if prev is None or not _is_valid_price(prev) or prev <= 0:
                    prev = current
                change = current - prev
                change_pct = (change / prev * 100) if prev and prev > 0 else 0.0
                vol = _safe_int(vol_series.iloc[-1]) if vol_series is not None and len(vol_series) else None
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
                )
            except FuturesTimeoutError:
                pass  # skip this ticker, may get it via yahooquery fallback
            except Exception as e:
                print(f"Warning: Retry range quote failed for {t}: {e}")

        # Fallback: yahooquery when yfinance failed (e.g. 401) for some tickers
        missing = [t for t in tickers if results[t] is None]
        if missing:
            fallback = MarketDataService._get_multiple_quotes_batch_with_range_yahooquery(
                missing, range_
            )
            for t, q in fallback.items():
                if q is not None:
                    results[t] = q
        return results

    # ---------- yahooquery fallback (when yfinance returns 401 or empty) ----------

    @staticmethod
    def _yq_coerce(v: Any) -> Optional[float]:
        """Extract float from yahooquery value (can be raw/fmt dict or number)."""
        if v is None:
            return None
        if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v):
            return float(v)
        if isinstance(v, dict):
            r = v.get("raw")
            if r is not None and isinstance(r, (int, float)):
                return float(r)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _get_market_status_from_yq(price: Dict[str, Any]) -> str:
        """Map yahooquery marketState to our market_status."""
        state = (price or {}).get("marketState") or ""
        if isinstance(state, dict):
            state = state.get("raw") or state.get("fmt") or ""
        s = str(state).upper()
        if s == "REGULAR":
            return "OPEN"
        if s == "CLOSED":
            return "CLOSED"
        if s == "PRE":
            return "PRE_MARKET"
        if s == "POST":
            return "AFTER_HOURS"
        return "UNKNOWN"

    @staticmethod
    def _ticker_quote_from_yahooquery_price(
        ticker: str, price: Dict[str, Any], summary_detail: Optional[Dict[str, Any]] = None
    ) -> Optional[TickerQuote]:
        """Build TickerQuote from yahooquery price (and optional summaryDetail)."""
        if not price or not isinstance(price, dict):
            return None
        summary_detail = summary_detail or {}
        current_price = MarketDataService._yq_coerce(
            price.get("regularMarketPrice") or price.get("regularMarketPreviousClose")
        )
        if current_price is None or not _is_valid_price(current_price):
            return None
        prev_close = MarketDataService._yq_coerce(
            price.get("regularMarketPreviousClose") or summary_detail.get("previousClose")
        )
        if prev_close is None or not _is_valid_price(prev_close):
            prev_close = current_price
        change_pct_raw = MarketDataService._yq_coerce(price.get("regularMarketChangePercent"))
        if change_pct_raw is not None:
            # yahooquery can return fractional (e.g. -0.016) or percentage (e.g. -1.6)
            if abs(change_pct_raw) <= 1.5:
                change_pct = change_pct_raw * 100.0
            else:
                change_pct = change_pct_raw
            daily_change = (change_pct / 100.0) * prev_close if prev_close else 0.0
        else:
            daily_change = current_price - prev_close
            change_pct = (daily_change / prev_close * 100.0) if prev_close and prev_close > 0 else 0.0
        return TickerQuote(
            ticker=ticker.upper(),
            current_price=round(current_price, 2),
            daily_change=round(daily_change, 2),
            daily_change_percent=round(change_pct, 2),
            bid_price=MarketDataService._yq_coerce(price.get("bid")),
            ask_price=MarketDataService._yq_coerce(price.get("ask")),
            bid_size=None,
            ask_size=None,
            volume=_safe_int(MarketDataService._yq_coerce(price.get("regularMarketVolume") or summary_detail.get("volume"))),
            previous_close=round(prev_close, 2),
            day_high=MarketDataService._yq_coerce(price.get("regularMarketDayHigh")),
            day_low=MarketDataService._yq_coerce(price.get("regularMarketDayLow")),
            fifty_two_week_high=MarketDataService._yq_coerce(
                summary_detail.get("fiftyTwoWeekHigh") or price.get("fiftyTwoWeekHigh")
            ),
            fifty_two_week_low=MarketDataService._yq_coerce(
                summary_detail.get("fiftyTwoWeekLow") or price.get("fiftyTwoWeekLow")
            ),
            market_status=MarketDataService._get_market_status_from_yq(price),
            last_update_time=datetime.now(),
        )

    @staticmethod
    def get_current_quote_yahooquery(ticker: str) -> Optional[TickerQuote]:
        """Fetch single quote via yahooquery (fallback when yfinance returns 401/empty)."""
        try:
            from yahooquery import Ticker as YahooQueryTicker
        except ImportError:
            return None
        ticker = ticker.upper()
        try:
            tq = YahooQueryTicker(ticker)
            raw = tq.get_modules("price summaryDetail")
            if not isinstance(raw, dict):
                raw = {}
            per = raw.get(ticker) or raw.get(ticker.lower())
            if not isinstance(per, dict):
                return None
            price = per.get("price") if isinstance(per.get("price"), dict) else {}
            summary = per.get("summaryDetail") if isinstance(per.get("summaryDetail"), dict) else {}
            quote = MarketDataService._ticker_quote_from_yahooquery_price(ticker, price, summary)
            if quote is not None:
                return quote
            # No price module: try history(period="5d") and build from close series
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
            )
        except Exception:
            return None

    @staticmethod
    def _get_multiple_quotes_batch_yahooquery(tickers: List[str]) -> Dict[str, Optional[TickerQuote]]:
        """Batch fetch quotes via yahooquery (fallback when yfinance fails)."""
        if not tickers:
            return {}
        results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
        try:
            from yahooquery import Ticker as YahooQueryTicker
        except ImportError:
            return results
        batch_size = 25
        for i in range(0, len(tickers), batch_size):
            chunk = [t.upper() for t in tickers[i : i + batch_size]]
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
                    quote = MarketDataService._ticker_quote_from_yahooquery_price(t, price, summary)
                    if quote is not None:
                        results[t] = quote
            except Exception:
                continue
        # Single-ticker fallback for any still missing (e.g. batch returned empty for one symbol)
        for t in tickers:
            if results.get(t) is None:
                q = MarketDataService.get_current_quote_yahooquery(t)
                if q is not None:
                    results[t] = q
        return results

    @staticmethod
    def _get_multiple_quotes_batch_with_range_yahooquery(
        tickers: List[str],
        range_: Literal["1d", "1w", "1mo", "3mo", "6mo", "ytd"],
    ) -> Dict[str, Optional[TickerQuote]]:
        """Fetch range-based quotes via yahooquery history() (fallback when yfinance fails)."""
        if not tickers:
            return {}
        results: Dict[str, Optional[TickerQuote]] = {t: None for t in tickers}
        try:
            from yahooquery import Ticker as YahooQueryTicker
        except ImportError:
            return results
        period = MARKET_RANGE_PERIODS.get(range_, "1mo")
        offset = MARKET_RANGE_OFFSETS.get(range_)
        batch_size = 25
        for i in range(0, len(tickers), batch_size):
            chunk = [t.upper() for t in tickers[i : i + batch_size]]
            try:
                tq = YahooQueryTicker(chunk)
                df = tq.history(period=period, interval="1d")
                if df is None or df.empty:
                    continue
                cols = getattr(df, "columns", None)
                if cols is None:
                    continue
                # yahooquery history: lowercase 'close', 'volume'; MultiIndex (symbol, date) or flat
                has_multi = hasattr(df.index, "levels") and len(df.index.names) >= 2
                if has_multi:
                    level0 = df.index.get_level_values(0)
                    sym_to_key = {str(s).upper(): s for s in level0.unique()}
                    for t in chunk:
                        key = sym_to_key.get(t) or sym_to_key.get(t.upper())
                        if key is None:
                            continue
                        try:
                            sub = df.xs(key, level=0)
                            close_series = sub["close"].dropna() if "close" in sub.columns else None
                        except (KeyError, TypeError):
                            continue
                        if close_series is None or len(close_series) < 1:
                            continue
                        current = _safe_float(close_series.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            continue
                        if offset is not None and len(close_series) >= 2:
                            prev = (
                                _safe_float(close_series.iloc[-offset])
                                if len(close_series) >= offset
                                else _safe_float(close_series.iloc[0])
                            )
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
                        if "volume" in sub.columns:
                            vol = _safe_int(sub["volume"].iloc[-1])
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
                        )
                else:
                    if len(chunk) != 1:
                        continue
                    t = chunk[0]
                    close_series = df["close"].dropna() if "close" in df.columns else None
                    if close_series is None or len(close_series) < 1:
                        continue
                    current = _safe_float(close_series.iloc[-1])
                    if current is None or not _is_valid_price(current):
                        continue
                    if offset is not None and len(close_series) >= 2:
                        prev = (
                            _safe_float(close_series.iloc[-offset])
                            if len(close_series) >= offset
                            else _safe_float(close_series.iloc[0])
                        )
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
                    vol = _safe_int(df["volume"].iloc[-1]) if "volume" in df.columns else None
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
                    )
            except Exception:
                continue
        return results

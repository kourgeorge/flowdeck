"""Service to fetch real-time market data using yfinance."""

import math
import yfinance as yf
import pandas as pd
from typing import List, Optional, Dict
from datetime import datetime
from models.schemas import StockQuote


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
    def get_current_quote(ticker: str) -> Optional[StockQuote]:
        """Get current market quote for a ticker."""
        try:
            ticker_obj = yf.Ticker(ticker.upper())
            info = ticker_obj.info
            fast_info = ticker_obj.fast_info
            
            # Get current price
            current_price = fast_info.get('lastPrice') or info.get('currentPrice') or info.get('regularMarketPrice')
            if current_price is None or not _is_valid_price(current_price):
                return None
            
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
            
            return StockQuote(
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
            return None
    
    @staticmethod
    def get_multiple_quotes(tickers: List[str]) -> Dict[str, Optional[StockQuote]]:
        """Get quotes for multiple tickers (sequential fallback). Prefer get_multiple_quotes_batch for speed."""
        return MarketDataService.get_multiple_quotes_batch(tickers)

    @staticmethod
    def get_multiple_quotes_batch(tickers: List[str]) -> Dict[str, Optional[StockQuote]]:
        """Fetch quotes for multiple tickers in one batch request via yf.download."""
        if not tickers:
            return {}
        tickers = [t.upper() for t in tickers]
        results: Dict[str, Optional[StockQuote]] = {t: None for t in tickers}
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
            if data.empty:
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

                if close_series is not None and len(close_series) >= 2:
                    current = _safe_float(close_series.iloc[-1])
                    if current is None or not _is_valid_price(current):
                        pass
                    else:
                        prev = _safe_float(close_series.iloc[-2])
                        if prev is None or not _is_valid_price(prev):
                            # If previous close is invalid, use current as both (0% change)
                            prev = current
                        daily_change = current - prev
                        daily_change_percent = (daily_change / prev * 100) if prev and prev > 0 else 0.0
                        results[t] = StockQuote(
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
                    current = _safe_float(close_series.iloc[-1])
                    if current is not None and _is_valid_price(current):
                        results[t] = StockQuote(
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
                        if len(close_series) < 1:
                            continue
                        current = _safe_float(close_series.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            continue
                        if len(close_series) >= 2:
                            prev = _safe_float(close_series.iloc[-2])
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
                        results[t] = StockQuote(
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
        return results

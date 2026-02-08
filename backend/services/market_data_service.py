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
        return p > 0 and not math.isnan(p)
    except (TypeError, ValueError):
        return False


class MarketDataService:
    """Service for fetching real-time market data."""
    
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
            
            # Get previous close
            previous_close = fast_info.get('previousClose') or info.get('previousClose') or info.get('regularMarketPreviousClose')
            
            # Calculate change
            if previous_close:
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
                auto_adjust=True,
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
                close_series = data["Close"] if "Close" in data.columns else None
                if close_series is not None and len(close_series) >= 2:
                    current = float(close_series.iloc[-1])
                    if not _is_valid_price(current):
                        pass
                    else:
                        prev = float(close_series.iloc[-2])
                        daily_change = current - prev
                        daily_change_percent = (daily_change / prev) * 100 if prev else 0.0
                        results[t] = StockQuote(
                            ticker=t,
                            current_price=round(current, 2),
                            daily_change=round(daily_change, 2),
                            daily_change_percent=round(daily_change_percent, 2),
                            bid_price=None,
                            ask_price=None,
                            bid_size=None,
                            ask_size=None,
                            volume=int(data["Volume"].iloc[-1]) if "Volume" in data.columns else None,
                            previous_close=round(prev, 2),
                            day_high=round(float(data["High"].iloc[-1]), 2) if "High" in data.columns else None,
                            day_low=round(float(data["Low"].iloc[-1]), 2) if "Low" in data.columns else None,
                            fifty_two_week_high=None,
                            fifty_two_week_low=None,
                            market_status="UNKNOWN",
                            last_update_time=datetime.now(),
                        )
                elif close_series is not None and len(close_series) == 1:
                    current = float(close_series.iloc[-1])
                    if _is_valid_price(current):
                        results[t] = StockQuote(
                            ticker=t,
                            current_price=round(current, 2),
                            daily_change=0.0,
                            daily_change_percent=0.0,
                            bid_price=None,
                            ask_price=None,
                            bid_size=None,
                            ask_size=None,
                            volume=int(data["Volume"].iloc[-1]) if "Volume" in data.columns else None,
                            previous_close=round(current, 2),
                            day_high=round(float(data["High"].iloc[-1]), 2) if "High" in data.columns else None,
                            day_low=round(float(data["Low"].iloc[-1]), 2) if "Low" in data.columns else None,
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
                        current = float(close_series.iloc[-1])
                        if not _is_valid_price(current):
                            continue
                        prev = float(close_series.iloc[-2]) if len(close_series) >= 2 else current
                        daily_change = current - prev
                        daily_change_percent = (daily_change / prev) * 100 if prev else 0.0
                        vol = None
                        high = low = None
                        if isinstance(data.columns, pd.MultiIndex):
                            if (t, "Volume") in data.columns:
                                vol = int(data[(t, "Volume")].iloc[-1])
                            if (t, "High") in data.columns:
                                high = round(float(data[(t, "High")].iloc[-1]), 2)
                            if (t, "Low") in data.columns:
                                low = round(float(data[(t, "Low")].iloc[-1]), 2)
                        else:
                            if "Volume" in data.columns and t in data["Volume"].columns:
                                vol = int(data["Volume"][t].iloc[-1])
                            if "High" in data.columns and t in data["High"].columns:
                                high = round(float(data["High"][t].iloc[-1]), 2)
                            if "Low" in data.columns and t in data["Low"].columns:
                                low = round(float(data["Low"][t].iloc[-1]), 2)
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
                            previous_close=round(prev, 2),
                            day_high=high,
                            day_low=low,
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


from langchain_core.tools import tool
from typing import Annotated
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ...dataflows.interface import route_to_vendor
from ...dataflows.config import get_config
import yfinance as yf
import os


@tool
def detect_divergence(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "indicator to check for divergence (rsi, macd, or macdh)"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back for divergence detection"] = 60,
) -> str:
    """
    Detect bullish or bearish divergence between price and technical indicators.
    Divergence occurs when price makes new highs/lows but the indicator doesn't, or vice versa.
    
    Args:
        symbol: Ticker symbol (e.g., AAPL, IBRX)
        indicator: Indicator to check (rsi, macd, or macdh)
        curr_date: Current trading date in YYYY-mm-dd format
        look_back_days: Number of days to analyze (default 60)
    
    Returns:
        String containing divergence analysis with detected signals and interpretation
    """
    try:
        # Get stock data
        try:
            curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
            start_date = (curr_date_dt - relativedelta(days=look_back_days + 30)).strftime("%Y-%m-%d")
            end_date = curr_date
        except ValueError as e:
            return f"Error: Invalid date format '{curr_date}'. Expected YYYY-MM-DD format. Please check the date and try again."
        
        try:
            # Call route_to_vendor directly instead of the tool wrapper
            stock_data_str = route_to_vendor("get_ticker_data", symbol, start_date, end_date)
        except Exception as e:
            return f"Error: Failed to retrieve stock data for {symbol}. Underlying error: {str(e)}. Please verify the ticker symbol is correct and the data vendor is accessible."
        
        # Validate stock data response
        if not stock_data_str or not isinstance(stock_data_str, str):
            return f"Error: Invalid response from stock data service for {symbol}. Received empty or non-string data."
        
        if stock_data_str.startswith("Error:") or "No data found" in stock_data_str or "error" in stock_data_str.lower():
            return f"Error: Stock data retrieval failed for {symbol}. Response: {stock_data_str}. Please verify the ticker symbol is valid and trading data exists for the specified date range ({start_date} to {end_date})."
        
        # Parse stock data
        lines = stock_data_str.split('\n')
        data_lines = [l for l in lines if l and not l.startswith('#')]
        if len(data_lines) < 2:
            return f"Error: Insufficient stock data for {symbol}. Received data does not contain enough rows. Please check if {symbol} has trading data for the date range {start_date} to {end_date}."
        
        # Parse CSV data with validation
        try:
            headers = data_lines[0].split(',')
            if not headers or len(headers) < 5:
                return f"Error: Invalid CSV structure for {symbol}. Expected columns: Date, Open, High, Low, Close, Volume. Please verify the data source is returning properly formatted data."
            
            data_rows = [row.split(',') for row in data_lines[1:] if row.strip()]
            if not data_rows:
                return f"Error: No data rows found for {symbol}. Please check if trading data exists for the date range."
            
            df = pd.DataFrame(data_rows, columns=headers)
            
            # Validate required columns exist
            required_cols = ['Date', 'Close', 'High', 'Low']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return f"Error: Missing required columns in stock data for {symbol}: {', '.join(missing_cols)}. Available columns: {', '.join(df.columns)}"
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['High'] = pd.to_numeric(df['High'], errors='coerce')
            df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
            
            # Check for valid data after parsing
            invalid_dates = df['Date'].isna().sum()
            invalid_prices = df[['Close', 'High', 'Low']].isna().all(axis=1).sum()
            if invalid_dates > len(df) * 0.5 or invalid_prices > len(df) * 0.5:
                return f"Error: Too many invalid data points for {symbol}. {invalid_dates} invalid dates, {invalid_prices} rows with invalid prices. Data may be corrupted or improperly formatted."
            
            df = df.dropna(subset=['Date', 'Close'])
            df = df.sort_values('Date')
            df = df.tail(look_back_days)
            
            if len(df) < 20:
                return f"Error: Insufficient data points for divergence analysis. Need at least 20 trading days, but only found {len(df)} valid data points for {symbol} in the date range {start_date} to {end_date}. Try increasing look_back_days or check if the stock has sufficient trading history."
        except Exception as e:
            return f"Error: Failed to parse stock data for {symbol}. Data parsing error: {str(e)}. Please verify the data format is correct."
        
        # Get indicator data
        try:
            # Call route_to_vendor directly instead of the tool wrapper
            indicator_data_str = route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)
        except Exception as e:
            return f"Error: Failed to retrieve indicator data for {symbol} ({indicator}). Underlying error: {str(e)}. Please verify the indicator name is correct and the data vendor is accessible."
        
        # Validate indicator data response
        if not indicator_data_str or not isinstance(indicator_data_str, str):
            return f"Error: Invalid response from indicator service for {symbol} ({indicator}). Received empty or non-string data."
        
        if indicator_data_str.startswith("Error:") or "error" in indicator_data_str.lower() or "not supported" in indicator_data_str.lower():
            return f"Error: Indicator data retrieval failed for {symbol} ({indicator}). Response: {indicator_data_str}. Please verify the indicator name '{indicator}' is valid. Supported indicators: rsi, macd, macdh, macds, close_50_sma, close_200_sma, close_10_ema, atr, boll, boll_ub, boll_lb, vwma."
        
        # Parse indicator data with validation
        try:
            indicator_lines = indicator_data_str.split('\n')
            indicator_dict = {}
            valid_indicator_count = 0
            
            for line in indicator_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Split only on the first colon to handle values that contain colons
                if ':' in line:
                    # Use split with maxsplit=1 to only split on first colon
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        date_str = parts[0].strip()
                        value_str = parts[1].strip()
                        
                        # Skip N/A values and empty values
                        if not value_str or 'N/A' in value_str.upper() or 'Not a trading day' in value_str or 'not available' in value_str.lower():
                            continue
                        
                        try:
                            value = float(value_str)
                            # Validate the value is not NaN or infinite
                            if pd.isna(value) or not np.isfinite(value):
                                continue
                            indicator_dict[date_str] = value
                            valid_indicator_count += 1
                        except (ValueError, TypeError):
                            continue
            
            if valid_indicator_count < 10:
                # Provide diagnostic information
                sample_lines = [line.strip() for line in indicator_lines[:10] if line.strip() and not line.strip().startswith('#')]
                sample_info = "\n".join(sample_lines[:5]) if sample_lines else "No data lines found"
                return f"Error: Insufficient valid indicator data for {symbol} ({indicator}). Found only {valid_indicator_count} valid indicator values (need at least 10). This may indicate:\n- The indicator cannot be calculated for this stock\n- The date range is too short\n- Most dates in the range are non-trading days\n- The indicator data format may be unexpected\n\nSample of indicator data received (first 5 lines):\n{sample_info}\n\nPlease verify the indicator name '{indicator}' is correct and that {symbol} has sufficient trading history for the requested date range."
        except Exception as e:
            return f"Error: Failed to parse indicator data for {symbol} ({indicator}). Parsing error: {str(e)}. Please verify the indicator data format is correct."
        
        # Match dates and create combined dataframe
        try:
            df['indicator_value'] = df['Date'].dt.strftime('%Y-%m-%d').map(indicator_dict)
            df = df.dropna(subset=['indicator_value', 'Close'])
            df['indicator_value'] = pd.to_numeric(df['indicator_value'])
            
            if len(df) < 20:
                return f"Error: Insufficient matched data points for divergence analysis. After matching price and indicator data, only {len(df)} data points remain (need at least 20). This may indicate date misalignment between price and indicator data. Try adjusting the date range or look_back_days parameter."
        except Exception as e:
            return f"Error: Failed to match price and indicator data for {symbol}. Matching error: {str(e)}. Please verify both datasets have compatible date formats."
        
        # Find local peaks and troughs in price
        price_peaks = []
        price_troughs = []
        indicator_peaks = []
        indicator_troughs = []
        
        window = min(5, len(df) // 10)
        
        for i in range(window, len(df) - window):
            # Price peaks
            if df.iloc[i]['High'] == df.iloc[i-window:i+window+1]['High'].max():
                price_peaks.append((i, df.iloc[i]['Date'], df.iloc[i]['High']))
            # Price troughs
            if df.iloc[i]['Low'] == df.iloc[i-window:i+window+1]['Low'].min():
                price_troughs.append((i, df.iloc[i]['Date'], df.iloc[i]['Low']))
            # Indicator peaks
            if df.iloc[i]['indicator_value'] == df.iloc[i-window:i+window+1]['indicator_value'].max():
                indicator_peaks.append((i, df.iloc[i]['Date'], df.iloc[i]['indicator_value']))
            # Indicator troughs
            if df.iloc[i]['indicator_value'] == df.iloc[i-window:i+window+1]['indicator_value'].min():
                indicator_troughs.append((i, df.iloc[i]['Date'], df.iloc[i]['indicator_value']))
        
        # Analyze divergences
        results = []
        
        # Bearish divergence: Price makes higher high, indicator makes lower high
        if len(price_peaks) >= 2 and len(indicator_peaks) >= 2:
            recent_price_peaks = sorted(price_peaks, key=lambda x: x[1])[-2:]
            recent_ind_peaks = sorted(indicator_peaks, key=lambda x: x[1])[-2:]
            
            if (recent_price_peaks[1][2] > recent_price_peaks[0][2] and 
                recent_ind_peaks[1][2] < recent_ind_peaks[0][2]):
                results.append({
                    'type': 'Bearish Divergence',
                    'description': f'Price made higher high ({recent_price_peaks[0][2]:.2f} -> {recent_price_peaks[1][2]:.2f}) but {indicator.upper()} made lower high ({recent_ind_peaks[0][2]:.3f} -> {recent_ind_peaks[1][2]:.3f})',
                    'signal': 'BEARISH',
                    'strength': 'Strong'
                })
        
        # Bullish divergence: Price makes lower low, indicator makes higher low
        if len(price_troughs) >= 2 and len(indicator_troughs) >= 2:
            recent_price_troughs = sorted(price_troughs, key=lambda x: x[1])[-2:]
            recent_ind_troughs = sorted(indicator_troughs, key=lambda x: x[1])[-2:]
            
            if (recent_price_troughs[1][2] < recent_price_troughs[0][2] and 
                recent_ind_troughs[1][2] > recent_ind_troughs[0][2]):
                results.append({
                    'type': 'Bullish Divergence',
                    'description': f'Price made lower low ({recent_price_troughs[0][2]:.2f} -> {recent_price_troughs[1][2]:.2f}) but {indicator.upper()} made higher low ({recent_ind_troughs[0][2]:.3f} -> {recent_ind_troughs[1][2]:.3f})',
                    'signal': 'BULLISH',
                    'strength': 'Strong'
                })
        
        # Build report
        report = f"## Divergence Analysis for {symbol.upper()}\n\n"
        report += f"**Analysis Period**: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}\n"
        report += f"**Indicator Analyzed**: {indicator.upper()}\n\n"
        
        if results:
            report += "### Detected Divergences:\n\n"
            for i, result in enumerate(results, 1):
                report += f"**{i}. {result['type']}**\n"
                report += f"- {result['description']}\n"
                report += f"- **Signal**: {result['signal']}\n"
                report += f"- **Strength**: {result['strength']}\n\n"
            
            report += "### Interpretation:\n"
            for result in results:
                if result['signal'] == 'BULLISH':
                    report += f"- **{result['type']}**: Suggests potential upward reversal. Price is declining but momentum is improving, indicating weakening selling pressure.\n"
                else:
                    report += f"- **{result['type']}**: Suggests potential downward reversal. Price is rising but momentum is weakening, indicating weakening buying pressure.\n"
        else:
            report += "### No Significant Divergences Detected\n\n"
            report += "No clear divergence patterns were found between price and the indicator. This suggests:\n"
            report += "- Price and momentum are moving in sync\n"
            report += "- Current trend may continue in the same direction\n"
            report += "- No immediate reversal signals detected\n"
        
        report += f"\n**Current Price**: ${df.iloc[-1]['Close']:.2f}\n"
        report += f"**Current {indicator.upper()}**: {df.iloc[-1]['indicator_value']:.3f}\n"
        
        return report
        
    except ValueError as e:
        return f"Error in divergence detection: Invalid input parameter. {str(e)}. Please verify the ticker symbol '{symbol}', date '{curr_date}', and indicator '{indicator}' are correct."
    except KeyError as e:
        return f"Error in divergence detection: Missing required data field. {str(e)}. This may indicate the data structure has changed. Please check the data source."
    except Exception as e:
        return f"Error in divergence detection for {symbol}: Unexpected error occurred. {str(e)}. Please verify all inputs are correct and try again. If the issue persists, the data source may be temporarily unavailable."


@tool
def detect_regime(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back for regime detection"] = 60,
) -> str:
    """
    Detect current market regime (trending vs ranging, high vs low volatility).
    Uses volatility analysis and trend strength to classify market state.
    
    Args:
        symbol: Ticker symbol (e.g., AAPL, IBRX)
        curr_date: Current trading date in YYYY-mm-dd format
        look_back_days: Number of days to analyze (default 60)
    
    Returns:
        String containing regime classification and adaptive trading recommendations
    """
    try:
        # Get stock data
        try:
            curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
            start_date = (curr_date_dt - relativedelta(days=look_back_days + 30)).strftime("%Y-%m-%d")
            end_date = curr_date
        except ValueError as e:
            return f"Error: Invalid date format '{curr_date}'. Expected YYYY-MM-DD format. Please check the date and try again."
        
        try:
            # Call route_to_vendor directly instead of the tool wrapper
            stock_data_str = route_to_vendor("get_ticker_data", symbol, start_date, end_date)
        except Exception as e:
            return f"Error: Failed to retrieve stock data for {symbol}. Underlying error: {str(e)}. Please verify the ticker symbol is correct and the data vendor is accessible."
        
        # Validate stock data response
        if not stock_data_str or not isinstance(stock_data_str, str):
            return f"Error: Invalid response from stock data service for {symbol}. Received empty or non-string data."
        
        if stock_data_str.startswith("Error:") or "No data found" in stock_data_str or "error" in stock_data_str.lower():
            return f"Error: Stock data retrieval failed for {symbol}. Response: {stock_data_str}. Please verify the ticker symbol is valid and trading data exists for the specified date range ({start_date} to {end_date})."
        
        # Parse stock data with validation
        try:
            lines = stock_data_str.split('\n')
            data_lines = [l for l in lines if l and not l.startswith('#')]
            if len(data_lines) < 2:
                return f"Error: Insufficient stock data for {symbol}. Received data does not contain enough rows. Please check if {symbol} has trading data for the date range {start_date} to {end_date}."
            
            headers = data_lines[0].split(',')
            if not headers or len(headers) < 5:
                return f"Error: Invalid CSV structure for {symbol}. Expected columns: Date, Open, High, Low, Close, Volume. Please verify the data source is returning properly formatted data."
            
            data_rows = [row.split(',') for row in data_lines[1:] if row.strip()]
            if not data_rows:
                return f"Error: No data rows found for {symbol}. Please check if trading data exists for the date range."
            
            df = pd.DataFrame(data_rows, columns=headers)
            
            # Validate required columns exist
            required_cols = ['Date', 'Close', 'High', 'Low', 'Volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return f"Error: Missing required columns in stock data for {symbol}: {', '.join(missing_cols)}. Available columns: {', '.join(df.columns)}"
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['High'] = pd.to_numeric(df['High'], errors='coerce')
            df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
            
            # Check for valid data after parsing
            invalid_dates = df['Date'].isna().sum()
            invalid_prices = df[['Close', 'High', 'Low']].isna().all(axis=1).sum()
            if invalid_dates > len(df) * 0.5 or invalid_prices > len(df) * 0.5:
                return f"Error: Too many invalid data points for {symbol}. {invalid_dates} invalid dates, {invalid_prices} rows with invalid prices. Data may be corrupted or improperly formatted."
            
            df = df.dropna(subset=['Date', 'Close'])
            df = df.sort_values('Date')
            df = df.tail(look_back_days)
            
            if len(df) < 20:
                return f"Error: Insufficient data points for regime detection. Need at least 20 trading days, but only found {len(df)} valid data points for {symbol} in the date range {start_date} to {end_date}. Try increasing look_back_days or check if the stock has sufficient trading history."
        except Exception as e:
            return f"Error: Failed to parse stock data for {symbol}. Data parsing error: {str(e)}. Please verify the data format is correct."
        
        # Calculate returns and volatility with validation
        try:
            df['Returns'] = df['Close'].pct_change()
            df['TrueRange'] = np.maximum(
                df['High'] - df['Low'],
                np.maximum(
                    abs(df['High'] - df['Close'].shift(1)),
                    abs(df['Low'] - df['Close'].shift(1))
                )
            )
            
            # Validate calculations
            if df['TrueRange'].isna().all():
                return f"Error: Unable to calculate True Range for {symbol}. Price data may be invalid or insufficient."
            
            # Volatility regime
            if len(df) < 20:
                return f"Error: Insufficient data for volatility calculation. Need at least 20 data points, got {len(df)}."
            
            short_vol = df['TrueRange'].tail(20).mean()
            long_vol = df['TrueRange'].mean()
            
            if pd.isna(short_vol) or pd.isna(long_vol):
                return f"Error: Failed to calculate volatility metrics for {symbol}. True Range values may be invalid."
            
            vol_ratio = short_vol / long_vol if long_vol > 0 else 1.0
        except Exception as e:
            return f"Error: Failed to calculate volatility metrics for {symbol}. Calculation error: {str(e)}. Please verify the price data is valid."
        
        # Trend strength (using ADX-like calculation) with validation
        try:
            if len(df) < 28:  # Need at least 28 days for 14-period rolling windows
                return f"Error: Insufficient data for ADX calculation. Need at least 28 trading days for trend strength analysis, but only have {len(df)} data points for {symbol}."
            
            df['PlusDM'] = np.where(
                (df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
                np.maximum(df['High'] - df['High'].shift(1), 0),
                0
            )
            df['MinusDM'] = np.where(
                (df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
                np.maximum(df['Low'].shift(1) - df['Low'], 0),
                0
            )
            
            atr_14 = df['TrueRange'].rolling(14).mean()
            if atr_14.isna().all() or (atr_14 == 0).all():
                return f"Error: Unable to calculate ATR for {symbol}. True Range values may be invalid or all zero."
            
            plus_di = 100 * (df['PlusDM'].rolling(14).mean() / atr_14)
            minus_di = 100 * (df['MinusDM'].rolling(14).mean() / atr_14)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = dx.rolling(14).mean()
            
            current_adx = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
            avg_adx = adx.mean() if not pd.isna(adx.mean()) else 0
        except Exception as e:
            return f"Error: Failed to calculate trend strength (ADX) for {symbol}. Calculation error: {str(e)}. Please verify the price data is valid."
        
        # Moving average analysis
        sma_20 = df['Close'].rolling(20).mean()
        sma_50 = df['Close'].rolling(50).mean() if len(df) >= 50 else sma_20
        
        price_above_sma20 = df['Close'].iloc[-1] > sma_20.iloc[-1] if not pd.isna(sma_20.iloc[-1]) else False
        sma20_above_sma50 = sma_20.iloc[-1] > sma_50.iloc[-1] if not pd.isna(sma_20.iloc[-1]) and not pd.isna(sma_50.iloc[-1]) else False
        
        # Classify regime
        regimes = []
        
        # Volatility regime
        if vol_ratio > 1.3:
            volatility_regime = "High Volatility"
            regimes.append("HIGH_VOLATILITY")
        elif vol_ratio < 0.7:
            volatility_regime = "Low Volatility"
            regimes.append("LOW_VOLATILITY")
        else:
            volatility_regime = "Normal Volatility"
            regimes.append("NORMAL_VOLATILITY")
        
        # Trend regime
        if current_adx > 25 and current_adx > avg_adx:
            trend_regime = "Strong Trending"
            regimes.append("TRENDING")
            trend_direction = "UPTREND" if price_above_sma20 and sma20_above_sma50 else "DOWNTREND"
        elif current_adx < 20:
            trend_regime = "Ranging/Choppy"
            regimes.append("RANGING")
            trend_direction = "SIDEWAYS"
        else:
            trend_regime = "Weak Trending"
            regimes.append("WEAK_TREND")
            trend_direction = "MIXED"
        
        # Build report
        report = f"## Market Regime Analysis for {symbol.upper()}\n\n"
        report += f"**Analysis Period**: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}\n\n"
        
        report += "### Current Regime Classification:\n\n"
        report += f"**Volatility Regime**: {volatility_regime}\n"
        report += f"- Short-term volatility: {short_vol:.4f}\n"
        report += f"- Long-term volatility: {long_vol:.4f}\n"
        report += f"- Volatility ratio: {vol_ratio:.2f}\n\n"
        
        report += f"**Trend Regime**: {trend_regime}\n"
        report += f"- ADX (Trend Strength): {current_adx:.2f}\n"
        report += f"- Average ADX: {avg_adx:.2f}\n"
        report += f"- Trend Direction: {trend_direction}\n\n"
        
        report += "### Adaptive Trading Recommendations:\n\n"
        
        if "TRENDING" in regimes:
            report += "**Trending Market Detected**:\n"
            report += "- ✅ Use momentum indicators (MACD, RSI)\n"
            report += "- ✅ Follow trend direction - avoid counter-trend trades\n"
            report += "- ✅ Use moving averages for entry/exit signals\n"
            report += "- ⚠️ Avoid oscillators in strong trends (they may stay overbought/oversold)\n\n"
        elif "RANGING" in regimes:
            report += "**Ranging Market Detected**:\n"
            report += "- ✅ Use oscillators (RSI, Stochastic) for overbought/oversold levels\n"
            report += "- ✅ Trade range boundaries (support/resistance)\n"
            report += "- ✅ Mean reversion strategies work well\n"
            report += "- ⚠️ Avoid trend-following indicators (they give false signals)\n\n"
        
        if "HIGH_VOLATILITY" in regimes:
            report += "**High Volatility Environment**:\n"
            report += "- ⚠️ Wider stop-losses required\n"
            report += "- ⚠️ Position sizing should be reduced\n"
            report += "- ✅ Volatility breakouts more likely\n"
            report += "- ✅ ATR-based stops recommended\n\n"
        elif "LOW_VOLATILITY" in regimes:
            report += "**Low Volatility Environment**:\n"
            report += "- ✅ Tighter stop-losses possible\n"
            report += "- ✅ Normal position sizing\n"
            report += "- ⚠️ Breakouts may be false signals\n"
            report += "- ✅ Range-bound strategies preferred\n\n"
        
        report += f"**Current Price**: ${df['Close'].iloc[-1]:.2f}\n"
        report += f"**20-day SMA**: ${sma_20.iloc[-1]:.2f}\n" if not pd.isna(sma_20.iloc[-1]) else ""
        
        return report
        
    except ValueError as e:
        return f"Error in regime detection: Invalid input parameter. {str(e)}. Please verify the ticker symbol '{symbol}' and date '{curr_date}' are correct."
    except KeyError as e:
        return f"Error in regime detection: Missing required data field. {str(e)}. This may indicate the data structure has changed. Please check the data source."
    except Exception as e:
        return f"Error in regime detection for {symbol}: Unexpected error occurred. {str(e)}. Please verify all inputs are correct and try again. If the issue persists, the data source may be temporarily unavailable."


@tool
def detect_support_resistance(
    symbol: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back for support/resistance detection"] = 90,
) -> str:
    """
    Detect key support and resistance levels using price clustering, volume profile, and statistical significance.
    
    Args:
        symbol: Ticker symbol (e.g., AAPL, IBRX)
        curr_date: Current trading date in YYYY-mm-dd format
        look_back_days: Number of days to analyze (default 90)
    
    Returns:
        String containing identified support/resistance levels with strength ratings
    """
    try:
        # Get stock data
        try:
            curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
            start_date = (curr_date_dt - relativedelta(days=look_back_days + 30)).strftime("%Y-%m-%d")
            end_date = curr_date
        except ValueError as e:
            return f"Error: Invalid date format '{curr_date}'. Expected YYYY-MM-DD format. Please check the date and try again."
        
        try:
            # Call route_to_vendor directly instead of the tool wrapper
            stock_data_str = route_to_vendor("get_ticker_data", symbol, start_date, end_date)
        except Exception as e:
            return f"Error: Failed to retrieve stock data for {symbol}. Underlying error: {str(e)}. Please verify the ticker symbol is correct and the data vendor is accessible."
        
        # Validate stock data response
        if not stock_data_str or not isinstance(stock_data_str, str):
            return f"Error: Invalid response from stock data service for {symbol}. Received empty or non-string data."
        
        if stock_data_str.startswith("Error:") or "No data found" in stock_data_str or "error" in stock_data_str.lower():
            return f"Error: Stock data retrieval failed for {symbol}. Response: {stock_data_str}. Please verify the ticker symbol is valid and trading data exists for the specified date range ({start_date} to {end_date})."
        
        # Parse stock data with validation
        try:
            lines = stock_data_str.split('\n')
            data_lines = [l for l in lines if l and not l.startswith('#')]
            if len(data_lines) < 2:
                return f"Error: Insufficient stock data for {symbol}. Received data does not contain enough rows. Please check if {symbol} has trading data for the date range {start_date} to {end_date}."
            
            headers = data_lines[0].split(',')
            if not headers or len(headers) < 5:
                return f"Error: Invalid CSV structure for {symbol}. Expected columns: Date, Open, High, Low, Close, Volume. Please verify the data source is returning properly formatted data."
            
            data_rows = [row.split(',') for row in data_lines[1:] if row.strip()]
            if not data_rows:
                return f"Error: No data rows found for {symbol}. Please check if trading data exists for the date range."
            
            df = pd.DataFrame(data_rows, columns=headers)
            
            # Validate required columns exist
            required_cols = ['Date', 'Close', 'High', 'Low', 'Volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return f"Error: Missing required columns in stock data for {symbol}: {', '.join(missing_cols)}. Available columns: {', '.join(df.columns)}"
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['High'] = pd.to_numeric(df['High'], errors='coerce')
            df['Low'] = pd.to_numeric(df['Low'], errors='coerce')
            df['Volume'] = pd.to_numeric(df['Volume'], errors='coerce')
            
            # Check for valid data after parsing
            invalid_dates = df['Date'].isna().sum()
            invalid_prices = df[['Close', 'High', 'Low']].isna().all(axis=1).sum()
            invalid_volumes = df['Volume'].isna().sum()
            if invalid_dates > len(df) * 0.5 or invalid_prices > len(df) * 0.5:
                return f"Error: Too many invalid data points for {symbol}. {invalid_dates} invalid dates, {invalid_prices} rows with invalid prices. Data may be corrupted or improperly formatted."
            
            df = df.dropna(subset=['Date', 'Close', 'Volume'])
            df = df.sort_values('Date')
            df = df.tail(look_back_days)
            
            if len(df) < 30:
                return f"Error: Insufficient data points for support/resistance analysis. Need at least 30 trading days, but only found {len(df)} valid data points for {symbol} in the date range {start_date} to {end_date}. Try increasing look_back_days or check if the stock has sufficient trading history."
            
            # Validate volume data exists
            if df['Volume'].isna().all() or (df['Volume'] == 0).all():
                return f"Warning: No valid volume data available for {symbol}. Support/resistance analysis will proceed without volume profile, but results may be less accurate."
        except Exception as e:
            return f"Error: Failed to parse stock data for {symbol}. Data parsing error: {str(e)}. Please verify the data format is correct."
        
        current_price = df['Close'].iloc[-1]
        
        # Method 1: Price clustering (find levels where price frequently reverses)
        price_bins = np.linspace(df['Low'].min(), df['High'].max(), 50)
        price_counts = np.zeros(len(price_bins) - 1)
        
        for _, row in df.iterrows():
            bin_idx = np.digitize([row['Close']], price_bins)[0] - 1
            if 0 <= bin_idx < len(price_counts):
                price_counts[bin_idx] += 1
        
        # Find clusters (local maxima in price distribution)
        cluster_levels = []
        for i in range(1, len(price_counts) - 1):
            if price_counts[i] > price_counts[i-1] and price_counts[i] > price_counts[i+1]:
                if price_counts[i] > np.percentile(price_counts, 75):
                    level = (price_bins[i] + price_bins[i+1]) / 2
                    cluster_levels.append((level, price_counts[i], 'cluster'))
        
        # Method 2: Volume Profile (price levels with highest volume)
        volume_profile = {}
        try:
            # Check if we have valid volume data
            valid_volume_df = df[df['Volume'].notna() & (df['Volume'] > 0)]
            if len(valid_volume_df) == 0:
                # Skip volume profile if no valid volume data
                pass
            else:
                for _, row in valid_volume_df.iterrows():
                    if pd.isna(row['Low']) or pd.isna(row['High']) or pd.isna(row['Volume']):
                        continue
                    try:
                        price_range = np.linspace(row['Low'], row['High'], 10)
                        for price in price_range:
                            rounded_price = round(price, 2)
                            volume_profile[rounded_price] = volume_profile.get(rounded_price, 0) + row['Volume'] / 10
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            # Continue without volume profile if calculation fails
            pass
        
        # Get top volume nodes
        sorted_volume = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        top_volume_levels = sorted_volume[:10]
        
        # Method 3: Recent highs and lows
        window = 20
        recent_highs = []
        recent_lows = []
        
        for i in range(window, len(df)):
            local_high = df.iloc[i-window:i+1]['High'].max()
            local_low = df.iloc[i-window:i+1]['Low'].min()
            
            if df.iloc[i]['High'] == local_high:
                recent_highs.append((df.iloc[i]['Date'], local_high))
            if df.iloc[i]['Low'] == local_low:
                recent_lows.append((df.iloc[i]['Date'], local_low))
        
        # Method 4: Moving averages as dynamic support/resistance
        sma_20 = df['Close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else None
        sma_50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else None
        sma_200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else None
        
        # Combine and classify levels
        all_levels = []
        
        # Add cluster levels
        for level, count, method in cluster_levels:
            if abs(level - current_price) / current_price < 0.15:  # Within 15% of current price
                all_levels.append({
                    'price': level,
                    'type': 'RESISTANCE' if level > current_price else 'SUPPORT',
                    'strength': 'Medium',
                    'method': 'Price Clustering',
                    'touches': int(count)
                })
        
        # Add volume profile levels
        for price, volume in top_volume_levels:
            if abs(price - current_price) / current_price < 0.15:
                strength = 'Strong' if volume > np.percentile([v for _, v in top_volume_levels], 80) else 'Medium'
                all_levels.append({
                    'price': price,
                    'type': 'RESISTANCE' if price > current_price else 'SUPPORT',
                    'strength': strength,
                    'method': 'Volume Profile',
                    'volume': volume
                })
        
        # Add recent highs/lows
        if recent_highs:
            recent_high = max([h[1] for h in recent_highs[-5:]])  # Last 5 highs
            if recent_high > current_price and abs(recent_high - current_price) / current_price < 0.15:
                all_levels.append({
                    'price': recent_high,
                    'type': 'RESISTANCE',
                    'strength': 'Strong',
                    'method': 'Recent High',
                    'touches': len([h for h in recent_highs if abs(h[1] - recent_high) / recent_high < 0.02])
                })
        
        if recent_lows:
            recent_low = min([l[1] for l in recent_lows[-5:]])  # Last 5 lows
            if recent_low < current_price and abs(recent_low - current_price) / current_price < 0.15:
                all_levels.append({
                    'price': recent_low,
                    'type': 'SUPPORT',
                    'strength': 'Strong',
                    'method': 'Recent Low',
                    'touches': len([l for l in recent_lows if abs(l[1] - recent_low) / recent_low < 0.02])
                })
        
        # Add moving averages
        for ma_name, ma_value in [('20 SMA', sma_20), ('50 SMA', sma_50), ('200 SMA', sma_200)]:
            if ma_value and abs(ma_value - current_price) / current_price < 0.15:
                all_levels.append({
                    'price': ma_value,
                    'type': 'DYNAMIC SUPPORT' if ma_value < current_price else 'DYNAMIC RESISTANCE',
                    'strength': 'Medium',
                    'method': ma_name,
                    'dynamic': True
                })
        
        # Remove duplicates (within 1% of each other) and sort
        unique_levels = []
        for level in sorted(all_levels, key=lambda x: x['price']):
            is_duplicate = False
            for existing in unique_levels:
                if abs(level['price'] - existing['price']) / existing['price'] < 0.01:
                    # Merge: keep the stronger one
                    if level['strength'] == 'Strong' and existing['strength'] != 'Strong':
                        unique_levels.remove(existing)
                        unique_levels.append(level)
                        is_duplicate = False
                        break
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_levels.append(level)
        
        # Build report
        report = f"## Support & Resistance Analysis for {symbol.upper()}\n\n"
        report += f"**Analysis Period**: {df['Date'].min().strftime('%Y-%m-%d')} to {df['Date'].max().strftime('%Y-%m-%d')}\n"
        report += f"**Current Price**: ${current_price:.2f}\n\n"
        
        # Separate support and resistance
        support_levels = [l for l in unique_levels if 'SUPPORT' in l['type']]
        resistance_levels = [l for l in unique_levels if 'RESISTANCE' in l['type']]
        
        if support_levels:
            report += "### Key Support Levels:\n\n"
            for level in sorted(support_levels, key=lambda x: x['price'], reverse=True):
                report += f"**${level['price']:.2f}** ({level['strength']} {level['type']})\n"
                report += f"- Detection Method: {level['method']}\n"
                if 'touches' in level:
                    report += f"- Price Touches: {level['touches']}\n"
                if 'dynamic' in level:
                    report += f"- Dynamic Level (moves with trend)\n"
                report += f"- Distance from Current: {((current_price - level['price']) / current_price * 100):.2f}%\n\n"
        
        if resistance_levels:
            report += "### Key Resistance Levels:\n\n"
            for level in sorted(resistance_levels, key=lambda x: x['price']):
                report += f"**${level['price']:.2f}** ({level['strength']} {level['type']})\n"
                report += f"- Detection Method: {level['method']}\n"
                if 'touches' in level:
                    report += f"- Price Touches: {level['touches']}\n"
                if 'dynamic' in level:
                    report += f"- Dynamic Level (moves with trend)\n"
                report += f"- Distance from Current: {((level['price'] - current_price) / current_price * 100):.2f}%\n\n"
        
        if not support_levels and not resistance_levels:
            report += "### No Significant Support/Resistance Levels Detected\n\n"
            report += "No clear support or resistance levels found within 15% of current price.\n"
        
        # Trading recommendations
        report += "### Trading Recommendations:\n\n"
        if support_levels:
            nearest_support = max([l['price'] for l in support_levels])
            report += f"- **Nearest Support**: ${nearest_support:.2f}\n"
            report += f"  - Consider buying near this level if price approaches\n"
            report += f"  - Set stop-loss below this level (e.g., ${nearest_support * 0.98:.2f})\n\n"
        
        if resistance_levels:
            nearest_resistance = min([l['price'] for l in resistance_levels])
            report += f"- **Nearest Resistance**: ${nearest_resistance:.2f}\n"
            report += f"  - Consider taking profits near this level\n"
            report += f"  - Watch for breakout above this level for continuation\n\n"
        
        return report
        
    except ValueError as e:
        return f"Error in support/resistance detection: Invalid input parameter. {str(e)}. Please verify the ticker symbol '{symbol}' and date '{curr_date}' are correct."
    except KeyError as e:
        return f"Error in support/resistance detection: Missing required data field. {str(e)}. This may indicate the data structure has changed. Please check the data source."
    except Exception as e:
        return f"Error in support/resistance detection for {symbol}: Unexpected error occurred. {str(e)}. Please verify all inputs are correct and try again. If the issue persists, the data source may be temporarily unavailable."

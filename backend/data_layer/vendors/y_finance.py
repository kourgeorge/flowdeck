from typing import Annotated, Any
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance as yf
import pandas as pd

# Make stockstats import optional - only needed for technical indicators
try:
    from .stockstats_utils import StockstatsUtils
except ImportError:
    StockstatsUtils = None  # Will be checked when used

def get_YFin_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    # Create ticker object
    ticker = yf.Ticker(symbol.upper())

    # Fetch historical data for the specified date range
    data = ticker.history(start=start_date, end=end_date)

    # Check if data is empty
    if data.empty:
        return (
            f"No data found for symbol '{symbol}' between {start_date} and {end_date}"
        )

    # Remove timezone info from index for cleaner output
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round numerical values to 2 decimal places for cleaner display
    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for col in numeric_columns:
        if col in data.columns:
            data[col] = data[col].round(2)

    # Convert DataFrame to CSV string
    csv_string = data.to_csv()

    # Add header information
    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string

def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:

    best_ind_params = {
        # Moving Averages
        "close_50_sma": (
            "50 SMA: A medium-term trend indicator. "
            "Usage: Identify trend direction and serve as dynamic support/resistance. "
            "Tips: It lags price; combine with faster indicators for timely signals."
        ),
        "close_200_sma": (
            "200 SMA: A long-term trend benchmark. "
            "Usage: Confirm overall market trend and identify golden/death cross setups. "
            "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
        ),
        "close_10_ema": (
            "10 EMA: A responsive short-term average. "
            "Usage: Capture quick shifts in momentum and potential entry points. "
            "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
        ),
        # MACD Related
        "macd": (
            "MACD: Computes momentum via differences of EMAs. "
            "Usage: Look for crossovers and divergence as signals of trend changes. "
            "Tips: Confirm with other indicators in low-volatility or sideways markets."
        ),
        "macds": (
            "MACD Signal: An EMA smoothing of the MACD line. "
            "Usage: Use crossovers with the MACD line to trigger trades. "
            "Tips: Should be part of a broader strategy to avoid false positives."
        ),
        "macdh": (
            "MACD Histogram: Shows the gap between the MACD line and its signal. "
            "Usage: Visualize momentum strength and spot divergence early. "
            "Tips: Can be volatile; complement with additional filters in fast-moving markets."
        ),
        # Momentum Indicators
        "rsi": (
            "RSI: Measures momentum to flag overbought/oversold conditions. "
            "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
            "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
        ),
        # Volatility Indicators
        "boll": (
            "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
            "Usage: Acts as a dynamic benchmark for price movement. "
            "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
        ),
        "boll_ub": (
            "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
            "Usage: Signals potential overbought conditions and breakout zones. "
            "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
        ),
        "boll_lb": (
            "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
            "Usage: Indicates potential oversold conditions. "
            "Tips: Use additional analysis to avoid false reversal signals."
        ),
        "atr": (
            "ATR: Averages true range to measure volatility. "
            "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
            "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
        ),
        # Volume-Based Indicators
        "vwma": (
            "VWMA: A moving average weighted by volume. "
            "Usage: Confirm trends by integrating price action with volume data. "
            "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
        ),
        "mfi": (
            "MFI: The Money Flow Index is a momentum indicator that uses both price and volume to measure buying and selling pressure. "
            "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength of trends or reversals. "
            "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI can indicate potential reversals."
        ),
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    end_date = curr_date
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    # Optimized: Get stock data once and calculate indicators for all dates
    try:
        indicator_data = _get_stock_stats_bulk(symbol, indicator, curr_date)
        
        # Generate the date range we need
        current_dt = curr_date_dt
        date_values = []
        
        while current_dt >= before:
            date_str = current_dt.strftime('%Y-%m-%d')
            
            # Look up the indicator value for this date
            if date_str in indicator_data:
                indicator_value = indicator_data[date_str]
            else:
                indicator_value = "N/A: Not a trading day (weekend or holiday)"
            
            date_values.append((date_str, indicator_value))
            current_dt = current_dt - relativedelta(days=1)
        
        # Build the result string
        ind_string = ""
        for date_str, value in date_values:
            ind_string += f"{date_str}: {value}\n"
        
    except Exception as e:
        print(f"Error getting bulk stockstats data: {e}")
        # Fallback to original implementation if bulk method fails
        ind_string = ""
        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        while curr_date_dt >= before:
            indicator_value = get_stockstats_indicator(
                symbol, indicator, curr_date_dt.strftime("%Y-%m-%d")
            )
            ind_string += f"{curr_date_dt.strftime('%Y-%m-%d')}: {indicator_value}\n"
            curr_date_dt = curr_date_dt - relativedelta(days=1)

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "No description available.")
    )

    return result_str


def _get_stock_stats_bulk(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to calculate"],
    curr_date: Annotated[str, "current date for reference"]
) -> dict:
    """
    Optimized bulk calculation of stock stats indicators.
    Fetches data once (cached in SQLite) and calculates indicator for all available dates.
    Returns dict mapping date strings to indicator values.
    """
    import io

    import pandas as pd
    from stockstats import wrap
    from services.data_cache import get_cached, get_cached_raw
    from config import DATA_CACHE_TTL_VENDOR_OHLCV

    cache_key = f"vendor_ohlcv:{symbol.upper()}"

    def _fetch_ohlcv() -> str:
        today_date = pd.Timestamp.today()
        end_date = today_date
        start_date = today_date - pd.DateOffset(years=15)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        try:
            downloaded = yf.download(
                symbol,
                start=start_str,
                end=end_str,
                multi_level_index=False,
                progress=False,
                auto_adjust=True,
            ).reset_index()
            if downloaded.empty or "Date" not in downloaded.columns:
                raise ValueError("Empty or invalid download")
            downloaded["Date"] = pd.to_datetime(downloaded["Date"], errors="coerce")
            downloaded = downloaded.dropna(subset=["Date"])
            if downloaded.empty:
                raise ValueError("No valid rows after dropna")
            return downloaded.to_csv(index=False)
        except Exception:
            fallback = get_cached_raw(cache_key)
            if fallback:
                return fallback
            raise Exception(
                f"Stockstats fail: no valid cached YFinance data available for {symbol}"
            )

    csv_str = get_cached(cache_key, DATA_CACHE_TTL_VENDOR_OHLCV, _fetch_ohlcv)
    data = pd.read_csv(io.StringIO(csv_str))
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])
    df = wrap(data)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    
    # Calculate the indicator for all rows at once
    df[indicator]  # This triggers stockstats to calculate the indicator
    
    # Create a dictionary mapping date strings to indicator values
    result_dict = {}
    for _, row in df.iterrows():
        date_str = row["Date"]
        indicator_value = row[indicator]
        
        # Handle NaN/None values
        if pd.isna(indicator_value):
            result_dict[date_str] = "N/A"
        else:
            result_dict[date_str] = str(indicator_value)
    
    return result_dict


def get_stockstats_indicator(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[
        str, "The current trading date you are trading on, YYYY-mm-dd"
    ],
) -> str:

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    curr_date = curr_date_dt.strftime("%Y-%m-%d")

    try:
        if StockstatsUtils is None:
            raise ImportError("stockstats module is not installed. Please install it to use technical indicators.")
        indicator_value = StockstatsUtils.get_stock_stats(
            symbol,
            indicator,
            curr_date,
        )
    except Exception as e:
        print(
            f"Error getting stockstats indicator data for indicator {indicator} on {curr_date}: {e}"
        )
        return ""

    return str(indicator_value)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get balance sheet data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_balance_sheet
        else:
            data = ticker_obj.balance_sheet
            
        if data.empty:
            return f"No balance sheet data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Balance Sheet data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get cash flow data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_cashflow
        else:
            data = ticker_obj.cashflow
            
        if data.empty:
            return f"No cash flow data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Cash Flow data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get income statement data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        
        if freq.lower() == "quarterly":
            data = ticker_obj.quarterly_income_stmt
        else:
            data = ticker_obj.income_stmt
            
        if data.empty:
            return f"No income statement data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Income Statement data for {ticker.upper()} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_fundamentals_core(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
) -> dict:
    """Get fundamental data (overview) from yfinance as a JSON dictionary."""
    
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info
        
        if not info:
            return {}
        
        # Map yfinance info fields to frontend expected field names
        fundamentals_dict = {
            # Basic company info
            "QuoteType": info.get("quoteType"),
            "Symbol": info.get("symbol", ticker.upper()),
            "Name": info.get("longName") or info.get("shortName"),
            "Description": info.get("longBusinessSummary"),
            "Sector": info.get("sector"),
            "Industry": info.get("industry"),
            "Exchange": info.get("exchange"),
            "Currency": info.get("currency"),
            "Country": info.get("country"),
            
            # Valuation metrics
            "MarketCapitalization": info.get("marketCap"),
            "EnterpriseValue": info.get("enterpriseValue"),
            "TrailingPE": info.get("trailingPE"),
            "ForwardPE": info.get("forwardPE"),
            "PEGRatio": info.get("pegRatio"),
            "PriceToSalesRatioTTM": info.get("priceToSalesTrailing12Months"),
            "PriceToBookRatio": info.get("priceToBook"),
            "EVToRevenue": info.get("enterpriseToRevenue"),
            "EVToEBITDA": info.get("enterpriseToEbitda"),
            
            # Profitability
            "ProfitMargin": info.get("profitMargins"),
            "GrossProfitTTM": info.get("grossProfits"),
            "OperatingMarginTTM": info.get("operatingMargins"),
            "ReturnOnAssetsTTM": info.get("returnOnAssets"),
            "ReturnOnEquityTTM": info.get("returnOnEquity"),
            
            # Financial data
            "RevenueTTM": info.get("totalRevenue"),
            "RevenuePerShareTTM": info.get("revenuePerShare"),
            "EBITDA": info.get("ebitda"),
            "BookValue": info.get("bookValue"),
            
            # Earnings
            "EPS": info.get("trailingEps"),
            "DilutedEPSTTM": info.get("trailingEps"),
            
            # Growth
            "QuarterlyRevenueGrowthYOY": info.get("revenueQuarterlyGrowth"),
            "QuarterlyEarningsGrowthYOY": info.get("earningsQuarterlyGrowth"),
            
            # Dividends
            "DividendYield": info.get("dividendYield"),
            "DividendPerShare": info.get("dividendRate"),
            "DividendDate": info.get("dividendDate"),
            "ExDividendDate": info.get("exDividendDate"),
            
            # Market data
            "Beta": info.get("beta"),
            "52WeekHigh": info.get("fiftyTwoWeekHigh") or info.get("52WeekHigh"),
            "52WeekLow": info.get("fiftyTwoWeekLow") or info.get("52WeekLow"),
            "50DayMovingAverage": info.get("fiftyDayAverage") or info.get("50DayMovingAverage"),
            "200DayMovingAverage": info.get("twoHundredDayAverage") or info.get("200DayMovingAverage"),
            
            # Shares
            "SharesOutstanding": info.get("sharesOutstanding"),
            "SharesFloat": info.get("floatShares"),
            "PercentInsiders": info.get("heldPercentInsiders"),
            "PercentInstitutions": info.get("heldPercentInstitutions"),
            
            # Analyst data
            "AnalystTargetPrice": info.get("targetMeanPrice"),
            # Note: yfinance info doesn't provide breakdown of ratings, only overall recommendation
            # These fields are left as None - can be populated from recommendations DataFrame if needed
            "AnalystRatingStrongBuy": None,
            "AnalystRatingBuy": None,
            "AnalystRatingHold": None,
            "AnalystRatingSell": None,
            "AnalystRatingStrongSell": None,
            
            # Additional info
            "LatestQuarter": info.get("mostRecentQuarter"),
            "FiscalYearEnd": info.get("fiscalYearEnd"),
            "Address": info.get("address1") or info.get("address2"),
            "OfficialSite": info.get("website"),
            "CIK": info.get("cik"),
        }
        
        # Clean up None values and convert to proper types
        cleaned_dict = {}
        for key, value in fundamentals_dict.items():
            if value is not None:
                # Convert dates to strings if they're timestamps
                if isinstance(value, (int, float)) and key in ["DividendDate", "ExDividendDate", "LatestQuarter"]:
                    try:
                        from datetime import datetime
                        cleaned_dict[key] = datetime.fromtimestamp(value).strftime("%Y-%m-%d")
                    except (ValueError, OSError, OverflowError):
                        cleaned_dict[key] = value
                else:
                    cleaned_dict[key] = value
        
        return cleaned_dict
        
    except Exception as e:
        print(f"Error retrieving fundamentals core for {ticker}: {e}")
        return {}


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None
):
    """Get fundamental data (overview) from yfinance as a formatted string."""
    try:
        # Get JSON data from core function
        fundamentals_dict = get_fundamentals_core(ticker, curr_date)
        
        if not fundamentals_dict:
            return f"No fundamental data found for symbol '{ticker}'"
        
        # Build formatted output
        result = f"# Fundamental Data Overview for {ticker.upper()}\n"
        result += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Company Information
        result += "## Company Information\n"
        result += f"Name: {fundamentals_dict.get('Name', 'N/A')}\n"
        result += f"Sector: {fundamentals_dict.get('Sector', 'N/A')}\n"
        result += f"Industry: {fundamentals_dict.get('Industry', 'N/A')}\n"
        if fundamentals_dict.get('Description'):
            result += f"\nBusiness Summary:\n{fundamentals_dict.get('Description', 'N/A')}\n\n"
        
        # Valuation Metrics
        result += "## Valuation Metrics\n"
        valuation_metrics = {
            'Market Cap': fundamentals_dict.get('MarketCapitalization'),
            'Enterprise Value': fundamentals_dict.get('EnterpriseValue'),
            'Trailing P/E': fundamentals_dict.get('TrailingPE'),
            'Forward P/E': fundamentals_dict.get('ForwardPE'),
            'PEG Ratio': fundamentals_dict.get('PEGRatio'),
            'Price to Sales (TTM)': fundamentals_dict.get('PriceToSalesRatioTTM'),
            'Price to Book': fundamentals_dict.get('PriceToBookRatio'),
            'Enterprise to Revenue': fundamentals_dict.get('EVToRevenue'),
            'Enterprise to EBITDA': fundamentals_dict.get('EVToEBITDA'),
        }
        for key, value in valuation_metrics.items():
            if value is not None:
                if isinstance(value, (int, float)):
                    if abs(value) >= 1e9:
                        result += f"{key}: ${value/1e9:.2f}B\n"
                    elif abs(value) >= 1e6:
                        result += f"{key}: ${value/1e6:.2f}M\n"
                    else:
                        result += f"{key}: {value:.2f}\n"
                else:
                    result += f"{key}: {value}\n"
        
        # Profitability Metrics
        result += "\n## Profitability Metrics\n"
        profitability_metrics = {
            'Profit Margins': fundamentals_dict.get('ProfitMargin'),
            'Gross Profit (TTM)': fundamentals_dict.get('GrossProfitTTM'),
            'Operating Margins': fundamentals_dict.get('OperatingMarginTTM'),
            'Return on Assets': fundamentals_dict.get('ReturnOnAssetsTTM'),
            'Return on Equity': fundamentals_dict.get('ReturnOnEquityTTM'),
        }
        for key, value in profitability_metrics.items():
            if value is not None:
                if isinstance(value, (int, float)):
                    if 'Margin' in key or 'Return' in key:
                        result += f"{key}: {value*100:.2f}%\n"
                    else:
                        if abs(value) >= 1e9:
                            result += f"{key}: ${value/1e9:.2f}B\n"
                        elif abs(value) >= 1e6:
                            result += f"{key}: ${value/1e6:.2f}M\n"
                        else:
                            result += f"{key}: ${value:.2f}\n"
                else:
                    result += f"{key}: {value}\n"
        
        # Growth Metrics
        result += "\n## Growth Metrics\n"
        growth_metrics = {
            'Revenue Growth (Quarterly YOY)': fundamentals_dict.get('QuarterlyRevenueGrowthYOY'),
            'Earnings Growth (Quarterly YOY)': fundamentals_dict.get('QuarterlyEarningsGrowthYOY'),
        }
        for key, value in growth_metrics.items():
            if value is not None:
                if isinstance(value, (int, float)):
                    result += f"{key}: {value*100:.2f}%\n"
                else:
                    result += f"{key}: {value}\n"
        
        # Financial Data
        result += "\n## Financial Data\n"
        financial_data = {
            'Total Revenue (TTM)': fundamentals_dict.get('RevenueTTM'),
            'EBITDA': fundamentals_dict.get('EBITDA'),
            'Book Value': fundamentals_dict.get('BookValue'),
            'Shares Outstanding': fundamentals_dict.get('SharesOutstanding'),
            'Float Shares': fundamentals_dict.get('SharesFloat'),
        }
        for key, value in financial_data.items():
            if value is not None:
                if isinstance(value, (int, float)):
                    if abs(value) >= 1e9:
                        result += f"{key}: ${value/1e9:.2f}B\n"
                    elif abs(value) >= 1e6:
                        result += f"{key}: ${value/1e6:.2f}M\n"
                    else:
                        result += f"{key}: {value:.2f}\n"
                else:
                    result += f"{key}: {value}\n"
        
        # Dividend Information
        result += "\n## Dividend Information\n"
        dividend_metrics = {
            'Dividend Yield': fundamentals_dict.get('DividendYield'),
            'Dividend per Share': fundamentals_dict.get('DividendPerShare'),
        }
        for key, value in dividend_metrics.items():
            if value is not None:
                if isinstance(value, (int, float)):
                    if key == 'Dividend Yield':
                        result += f"{key}: {value*100:.2f}%\n"
                    else:
                        result += f"{key}: ${value:.2f}\n"
                else:
                    result += f"{key}: {value}\n"
        
        return result
        
    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
):
    """Get insider transactions data from yfinance (string format for agents)."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        data = ticker_obj.insider_transactions

        if data is None or data.empty:
            return f"No insider transactions data found for symbol '{ticker}'"

        csv_string = data.to_csv()
        header = f"# Insider Transactions data for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        return f"Error retrieving insider transactions for {ticker}: {str(e)}"


def get_insider_transactions_app_format(ticker: str, limit: int = 50) -> dict:
    """Get insider transactions from yfinance. App API shape: {ticker, date, transactions, count}."""
    from typing import Any, Dict, List

    ticker = ticker.upper()
    curr_date = datetime.now().strftime("%Y-%m-%d")

    def _cell(row: Dict[str, Any], key: str) -> Any:
        val = row.get(key)
        if pd.isna(val):
            return None
        if hasattr(val, "isoformat"):
            try:
                return val.date().isoformat() if hasattr(val, "date") else val.isoformat()
            except Exception:
                return str(val)
        if hasattr(val, "item"):
            try:
                return val.item()
            except Exception:
                return str(val)
        return val

    try:
        raw_df = yf.Ticker(ticker).insider_transactions
    except Exception as e:
        return {"ticker": ticker, "date": curr_date, "transactions": [], "count": 0, "error": str(e)}
    if raw_df is None or raw_df.empty:
        return {"ticker": ticker, "date": curr_date, "transactions": [], "count": 0}
    df = raw_df.copy()
    if "Start Date" in df.columns:
        df = df.sort_values(by="Start Date", ascending=False, na_position="last")
    if limit > 0:
        df = df.head(limit)
    transactions = []
    for row in df.to_dict(orient="records"):
        transactions.append({
            "insider": _cell(row, "Insider"),
            "position": _cell(row, "Position"),
            "transaction": _cell(row, "Transaction"),
            "start_date": _cell(row, "Start Date"),
            "shares": _cell(row, "Shares"),
            "value": _cell(row, "Value"),
            "ownership": _cell(row, "Ownership"),
            "url": _cell(row, "URL"),
            "text": _cell(row, "Text"),
        })
    return {"ticker": ticker, "date": curr_date, "transactions": transactions, "count": len(transactions)}


def get_company_info(ticker: str) -> dict:
    """Get company profile (name, sector, industry, etc.) from yfinance. Fallback when yahooquery fails."""
    ticker = ticker.upper()
    default = {
        "name": ticker,
        "sector": "N/A",
        "industry": "N/A",
        "exchange": "N/A",
        "country": "N/A",
        "website": "N/A",
        "quoteType": "INDEX" if ticker.startswith("^") else None,
    }
    try:
        t = yf.Ticker(ticker)
        info = t.info
        quote_type = info.get("quoteType")
        if quote_type is None and ticker.startswith("^"):
            quote_type = "INDEX"
        return {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "exchange": info.get("exchange", "N/A"),
            "country": info.get("country", "N/A"),
            "website": info.get("website", "N/A"),
            "quoteType": quote_type,
        }
    except Exception:
        return default


def get_extended_info(ticker: str) -> dict:
    """Get extended metrics (beta, market cap, margins, etc.) from yfinance."""
    ticker = ticker.upper()
    empty = {"beta": None, "market_cap": None, "revenue": None, "gross_margin": None, "dividend_yield": None,
             "trailing_eps": None, "forward_eps": None, "average_volume": None, "enterprise_value": None,
             "profit_margin": None, "operating_margin": None, "ebitda": None, "pe_ratio": None, "forward_pe": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info
        try:
            hist = t.history(period="3mo")
            avg_volume = int(hist["Volume"].mean()) if not hist.empty and "Volume" in hist.columns else None
        except Exception:
            avg_volume = None
        return {
            "beta": info.get("beta"),
            "market_cap": info.get("marketCap"),
            "revenue": info.get("totalRevenue"),
            "gross_margin": info.get("grossMargins"),
            "dividend_yield": info.get("dividendYield"),
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "average_volume": avg_volume,
            "enterprise_value": info.get("enterpriseValue"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "ebitda": info.get("ebitda"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
        }
    except Exception:
        return empty


def get_company_officers(ticker: str) -> dict:
    """Get company officers from yfinance. App API shape."""
    ticker = ticker.upper()
    try:
        t = yf.Ticker(ticker)
        info = t.info
        officers_data = info.get("companyOfficers") or []
        officers = []
        for officer in officers_data:
            if not isinstance(officer, dict):
                continue
            name = officer.get("name")
            title = officer.get("title")
            if not name or not title:
                continue
            officers.append({
                "name": name,
                "title": title,
                "age": officer.get("age"),
                "year_born": officer.get("yearBorn"),
                "fiscal_year": officer.get("fiscalYear"),
                "total_pay": officer.get("totalPay"),
                "exercised_value": officer.get("exercisedValue"),
                "unexercised_value": officer.get("unexercisedValue"),
            })
        return {"ticker": ticker, "officers": officers, "count": len(officers)}
    except Exception:
        return {"ticker": ticker, "officers": [], "count": 0}


def get_fund_info(ticker: str) -> dict:
    """Get ETF/fund-specific data from yfinance."""
    ticker = ticker.upper()
    out = {"ticker": ticker, "totalAssets": None, "yield": None, "category": None, "fundInception": None,
           "expenseRatio": None, "description": None, "fund_overview": None, "top_holdings": None,
           "sector_weightings": None, "asset_classes": None}
    try:
        t = yf.Ticker(ticker)
        info = t.info
        out["totalAssets"] = info.get("totalAssets")
        out["yield"] = info.get("yield")
        out["category"] = info.get("category")
        out["fundInception"] = info.get("fundInception")
        out["expenseRatio"] = info.get("expenseRatio")
        try:
            fd = t.funds_data
            if fd is not None:
                out["description"] = getattr(fd, "description", None)
                out["fund_overview"] = getattr(fd, "fund_overview", None)
                th = getattr(fd, "top_holdings", None)
                if th is not None and hasattr(th, "to_dict"):
                    out["top_holdings"] = th.to_dict(orient="records")
                out["sector_weightings"] = getattr(fd, "sector_weightings", None)
                out["asset_classes"] = getattr(fd, "asset_classes", None)
        except Exception:
            pass
    except Exception:
        pass
    return out


def get_future_events(ticker: str) -> dict:
    """Get upcoming earnings and ex-dividend dates from yfinance."""
    import math
    from datetime import timezone

    ticker = ticker.upper()
    today = datetime.now().date()
    events = []
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        ex_ts = info.get("exDividendDate")
        if ex_ts is not None:
            try:
                ex_date = datetime.fromtimestamp(ex_ts, tz=timezone.utc).date()
            except Exception:
                ex_date = datetime.fromtimestamp(ex_ts).date()
            if ex_date >= today:
                events.append({"date": ex_date.strftime("%Y-%m-%d"), "type": "ex_dividend", "label": "Ex-dividend date"})
        try:
            ed = t.get_earnings_dates(limit=12)
            if ed is not None and not ed.empty:
                for idx, row in ed.iterrows():
                    d = idx
                    if hasattr(d, "tz_localize") and d.tzinfo is not None:
                        d = d.tz_localize(None)
                    if hasattr(d, "date"):
                        d = d.date()
                    if d < today:
                        continue
                    date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                    eps_est = row.get("EPS Estimate")
                    label = "Earnings"
                    eps_val = None
                    if eps_est is not None:
                        try:
                            fval = float(eps_est)
                            if not math.isnan(fval):
                                eps_val = fval
                                label = f"Earnings (EPS est. ${fval:.2f})"
                        except (TypeError, ValueError):
                            pass
                    events.append({"date": date_str, "type": "earnings", "label": label, "eps_estimate": eps_val})
        except Exception:
            pass
    except Exception:
        pass
    return {"ticker": ticker, "events": events, "count": len(events)}


def get_yfinance_news(
    ticker: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format (not used by yfinance, but kept for API compatibility)"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format (not used by yfinance, but kept for API compatibility)"],
) -> str:
    """Get news articles for a ticker from yfinance.
    
    Note: yfinance.news doesn't support date filtering and returns the most recent news articles.
    The start_date and end_date parameters are kept for API compatibility but are not used.
    
    Args:
        ticker: Ticker symbol
        start_date: Start date (not used, kept for compatibility)
        end_date: End date (not used, kept for compatibility)
    
    Returns:
        JSON string containing news articles
    """
    import json
    
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        news = ticker_obj.news
        
        if not news:
            return json.dumps({
                "ticker": ticker.upper(),
                "articles": [],
                "count": 0
            })
        
        # Format news articles
        articles = []
        for article in news:
            # Convert timestamp to readable date
            pub_time = article.get('providerPublishTime', 0)
            pub_date = datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d %H:%M:%S") if pub_time else None
            
            articles.append({
                "uuid": article.get('uuid', ''),
                "title": article.get('title', ''),
                "publisher": article.get('publisher', ''),
                "link": article.get('link', ''),
                "published_time": pub_date,
                "published_timestamp": pub_time,
                "type": article.get('type', ''),
                "thumbnail": article.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', '') if article.get('thumbnail') else None,
            })
        
        return json.dumps({
            "ticker": ticker.upper(),
            "articles": articles,
            "count": len(articles)
        })
        
    except Exception as e:
        return json.dumps({
            "ticker": ticker.upper(),
            "articles": [],
            "count": 0,
            "error": str(e)
        })


def get_analyst_recommendations(
    ticker: Annotated[str, "ticker symbol of the company"]
) -> dict:
    """Get analyst recommendations from yfinance.
    
    Args:
        ticker: Ticker symbol
    
    Returns:
        Dictionary containing recommendation summary and breakdown
    """
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        recommendations = ticker_obj.recommendations
        
        if recommendations is None or recommendations.empty:
            return {
                "ticker": ticker.upper(),
                "recommendation": None,
                "target_price": None,
                "breakdown": {},
                "total_analysts": 0,
                "latest_date": None
            }
        
        def _count_from_row(row: pd.Series, *keys: str) -> int:
            for key in keys:
                if key in row.index:
                    val = row[key]
                    if pd.notna(val):
                        try:
                            return int(val)
                        except Exception:
                            return 0
            return 0

        # Yahoo has two observed shapes:
        # 1) legacy columns: Strong Buy/Buy/Hold/Sell/Strong Sell with DatetimeIndex
        # 2) trend columns: period/strongBuy/buy/hold/sell/strongSell with integer index
        latest_date = None
        if "period" in recommendations.columns:
            rec_df = recommendations.copy()
            try:
                period_series = rec_df["period"].astype(str)
                zero_month_rows = rec_df[period_series == "0m"]
                latest_row = zero_month_rows.iloc[0] if not zero_month_rows.empty else rec_df.iloc[0]
            except Exception:
                latest_row = rec_df.iloc[0]
            # No explicit date in trend payload; keep None.
            latest_date = None
        else:
            if isinstance(recommendations.index, pd.DatetimeIndex):
                recommendations = recommendations.sort_index(ascending=False)
            latest_row = recommendations.iloc[0]
            latest_index = recommendations.index[0]
            if hasattr(latest_index, "strftime"):
                latest_date = latest_index.strftime("%Y-%m-%d")
            else:
                latest_date = str(latest_index)

        strong_buy = _count_from_row(latest_row, "Strong Buy", "strongBuy", "strong_buy")
        buy = _count_from_row(latest_row, "Buy", "buy")
        hold = _count_from_row(latest_row, "Hold", "hold")
        sell = _count_from_row(latest_row, "Sell", "sell")
        strong_sell = _count_from_row(latest_row, "Strong Sell", "strongSell", "strong_sell")

        breakdown = {
            "Strong Buy": strong_buy,
            "Buy": buy,
            "Hold": hold,
            "Sell": sell,
            "Strong Sell": strong_sell,
        }
        total = strong_buy + buy + hold + sell + strong_sell
        
        # Determine overall recommendation based on highest count
        recommendation = None
        if total > 0:
            max_count = max(breakdown.values())
            recommendation = [k for k, v in breakdown.items() if v == max_count][0]
            # Normalize to BUY/SELL/HOLD format
            if recommendation in ['Strong Buy', 'Buy']:
                recommendation = 'BUY'
            elif recommendation in ['Strong Sell', 'Sell']:
                recommendation = 'SELL'
            else:
                recommendation = 'HOLD'
        
        info = ticker_obj.info
        # Get target price from info
        target_price = info.get('targetMeanPrice') or info.get('targetHighPrice') or info.get('targetLowPrice')

        # Fallback recommendation from Yahoo key if counts are unavailable.
        if recommendation is None:
            key = str(info.get("recommendationKey") or "").strip().lower()
            if key in ("strong_buy", "buy"):
                recommendation = "BUY"
            elif key in ("strong_sell", "sell"):
                recommendation = "SELL"
            elif key in ("hold",):
                recommendation = "HOLD"
        
        return {
            "ticker": ticker.upper(),
            "recommendation": recommendation,
            "target_price": float(target_price) if target_price else None,
            "breakdown": breakdown,
            "total_analysts": total,
            "latest_date": latest_date
        }
        
    except Exception as e:
        print(f"Error retrieving analyst recommendations for {ticker}: {e}")
        return {
            "ticker": ticker.upper(),
            "recommendation": None,
            "target_price": None,
            "breakdown": {},
            "total_analysts": 0,
            "latest_date": None,
            "error": str(e)
        }


def get_historical_app_format(ticker: str, period: str = "6mo", interval: str = "1d") -> dict:
    """Fetch historical OHLCV from yfinance. App API shape: {ticker, period, interval, data, count}."""
    from datetime import date, timedelta

    ticker = ticker.upper()
    intraday_intervals = ("1m", "2m", "5m", "15m", "30m", "60m")
    use_last_trading_day = period == "1d" and interval in intraday_intervals
    try:
        ticker_obj = yf.Ticker(ticker)
        if use_last_trading_day:
            today = date.today()
            last_close = today - timedelta(days=3) if today.weekday() == 0 else today - timedelta(days=1)
            start = last_close.strftime("%Y-%m-%d")
            end = (last_close + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = ticker_obj.history(start=start, end=end, interval=interval)
        else:
            hist = ticker_obj.history(period=period, interval=interval)
    except Exception:
        return {"ticker": ticker, "period": period, "interval": interval, "data": [], "count": 0}
    if hist.empty:
        return {"ticker": ticker, "period": period, "interval": interval, "data": [], "count": 0}
    data = []
    for date_idx, row in hist.iterrows():
        d = date_idx
        if hasattr(d, "tz_localize") and d.tzinfo is not None:
            d = d.tz_localize(None)
        date_str = d.strftime("%Y-%m-%dT%H:%M:%S") if use_last_trading_day and hasattr(d, "strftime") else (d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d))
        adj_close = row.get("Adj Close") if "Adj Close" in row else row.get("Close")
        data.append({
            "date": date_str,
            "timestamp": int(d.timestamp() * 1000) if hasattr(d, "timestamp") else None,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if "Volume" in row else None,
            "adj_close": round(float(adj_close), 2) if adj_close is not None else None,
        })
    return {"ticker": ticker, "period": period, "interval": interval, "data": data, "count": len(data)}


def _to_json_safe_int(val: Any) -> int:
    """Convert to native Python int (handles numpy.int64, etc.) for JSON serialization."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def get_news_app_format(ticker: str, lookback_days: int = 7) -> dict:
    """Fetch ticker news from yfinance and return app API shape: {ticker, date, articles, count}."""
    from typing import Any, Dict, List

    ticker = ticker.upper()
    curr_date = datetime.now().strftime("%Y-%m-%d")

    def _safe_resolutions_first(thumb: dict) -> Any:
        res = thumb.get("resolutions")
        if isinstance(res, list) and res:
            return res[0]
        return None

    def _parse_article(raw: Dict[str, Any]):
        try:
            content = raw.get("content")
            if isinstance(content, dict):
                uuid = raw.get("id") or content.get("id", "")
                title = content.get("title", "")
                link = ""
                for key in ("canonicalUrl", "clickThroughUrl"):
                    u = content.get(key)
                    if isinstance(u, dict) and u.get("url"):
                        link = u["url"]
                        break
                provider = content.get("provider")
                publisher = provider.get("displayName", "") if isinstance(provider, dict) else ""
                pub_date_str = content.get("pubDate") or ""
                published_time = pub_date_str[:19].replace("T", " ") if pub_date_str else None
                published_timestamp = 0
                if pub_date_str:
                    try:
                        s = pub_date_str.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(s[:26])
                        published_timestamp = _to_json_safe_int(dt.timestamp())
                    except Exception:
                        pass
                thumb = content.get("thumbnail")
                thumb_url = None
                if isinstance(thumb, dict):
                    thumb_url = thumb.get("originalUrl")
                    if not thumb_url:
                        first = _safe_resolutions_first(thumb)
                        if isinstance(first, dict):
                            thumb_url = first.get("url")
                summary = content.get("summary") or content.get("description") or ""
                return {
                    "uuid": str(uuid),
                    "title": title or "",
                    "summary": summary if isinstance(summary, str) else "",
                    "publisher": publisher or "",
                    "link": link or "",
                    "published_time": published_time,
                    "published_timestamp": published_timestamp,
                    "type": content.get("contentType", ""),
                    "thumbnail": thumb_url,
                }
            pub_time = raw.get("providerPublishTime", 0)
            pub_date = None
            if pub_time:
                try:
                    pub_date = datetime.fromtimestamp(int(pub_time)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            thumb = raw.get("thumbnail")
            thumb_url = None
            if thumb and isinstance(thumb, dict):
                first = _safe_resolutions_first(thumb)
                if isinstance(first, dict):
                    thumb_url = first.get("url")
            summary = raw.get("summary") or raw.get("description") or ""
            return {
                "uuid": str(raw.get("uuid", raw.get("id", ""))),
                "title": str(raw.get("title", "")),
                "summary": summary if isinstance(summary, str) else "",
                "publisher": str(raw.get("publisher", "")),
                "link": str(raw.get("link", "")),
                "published_time": pub_date,
                "published_timestamp": _to_json_safe_int(pub_time),
                "type": str(raw.get("type", "")),
                "thumbnail": thumb_url,
            }
        except Exception:
            return None

    try:
        ticker_obj = yf.Ticker(ticker)
        news = ticker_obj.news
    except Exception as e:
        return {"ticker": ticker, "date": curr_date, "articles": [], "count": 0, "error": str(e)}
    if not news:
        return {"ticker": ticker, "date": curr_date, "articles": [], "count": 0}
    articles: List[Dict[str, Any]] = []
    for raw in news:
        item = _parse_article(raw)
        if item:
            articles.append(item)
    return {"ticker": ticker, "date": curr_date, "articles": articles, "count": len(articles)}


def get_financial_statements(
    ticker: str, statement_type: str = "all", freq: str = "quarterly"
) -> dict:
    """Fetch balance sheet, cashflow, income statement from yfinance. App API shape."""
    from typing import Any, Dict, List

    def _row_to_key(name: str) -> str:
        if not name or not isinstance(name, str):
            return ""
        parts = name.strip().split()
        if not parts:
            return ""
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _dataframe_to_reports(df) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        reports = []
        for col in df.columns:
            try:
                date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
            except Exception:
                date_str = str(col)[:10]
            report: Dict[str, Any] = {"fiscalDateEnding": date_str}
            for idx in df.index:
                key = _row_to_key(str(idx))
                if not key:
                    continue
                val = df.loc[idx, col]
                if val is None or (isinstance(val, float) and (val != val)):
                    report[key] = None
                else:
                    try:
                        report[key] = int(val) if isinstance(val, (int, float)) and float(val) == int(val) else float(val)
                    except (TypeError, ValueError):
                        report[key] = val
            reports.append(report)
        return reports

    ticker = ticker.upper()
    curr_date = datetime.now().strftime("%Y-%m-%d")
    result = {"ticker": ticker, "date": curr_date, "frequency": freq, "statements": {}}
    try:
        t = yf.Ticker(ticker)
        bs_ann, bs_qtr = t.balance_sheet, t.quarterly_balance_sheet
        cf_ann, cf_qtr = t.cashflow, t.quarterly_cashflow
        inc_ann, inc_qtr = t.income_stmt, t.quarterly_income_stmt
    except Exception as e:
        for key in ["balance_sheet", "cashflow", "income_statement"]:
            if statement_type in ("all", key):
                result["statements"][key] = {"format": "error", "data": str(e)}
        return result

    def add_stmt(key: str, df_ann, df_qtr) -> None:
        if statement_type not in ("all", key):
            return
        annual = _dataframe_to_reports(df_ann)
        quarterly = _dataframe_to_reports(df_qtr)
        result["statements"][key] = {"format": "json", "data": {"annualReports": annual, "quarterlyReports": quarterly}}

    add_stmt("balance_sheet", bs_ann, bs_qtr)
    add_stmt("cashflow", cf_ann, cf_qtr)
    add_stmt("income_statement", inc_ann, inc_qtr)
    return result


def get_financial_charts(ticker: str, freq: str = "annual") -> dict:
    """Fetch chart-ready financial series from yfinance. App API shape."""
    from typing import Any, Dict, List, Optional

    def _find_row(df, *candidates: str):
        if df is None or df.empty:
            return None
        idx_str = [str(i).lower() for i in df.index]
        for c in candidates:
            c_lower = c.lower()
            for i, s in enumerate(idx_str):
                if c_lower in s:
                    return df.index[i]
        return None

    def _period_to_key(p: str) -> str:
        return p[:7] if len(p) >= 7 else p

    def _align_series_to_periods(periods: List[str], df, row_label) -> List[Optional[float]]:
        if df is None or df.empty or row_label is None or row_label not in df.index:
            return [None] * len(periods)
        row = df.loc[row_label]
        key_to_val = {}
        for col, v in row.items():
            try:
                pk = _period_to_key(col.strftime("%Y-%m-%d")[:7] if hasattr(col, "strftime") else str(col)[:10])
                key_to_val[pk] = float(v) if v is not None and not (isinstance(v, float) and (v != v)) else None
            except (TypeError, ValueError):
                pass
        return [key_to_val.get(_period_to_key(p)) for p in periods]

    def _periods_from_df(df) -> List[str]:
        if df is None or df.empty:
            return []
        out = []
        for c in df.columns:
            try:
                if hasattr(c, "strftime"):
                    out.append(c.strftime("%Y-%m-%d")[:7] if hasattr(c, "month") else c.strftime("%Y"))
                else:
                    out.append(str(c)[:10])
            except Exception:
                out.append(str(c))
        return out

    ticker = ticker.upper()
    empty_resp = {
        "ticker": ticker,
        "frequency": freq,
        "historical_financials": None,
        "shares_outstanding": None,
        "long_term_debt_vs_fcf": None,
        "retained_earnings": None,
        "total_cash_vs_long_term_debt": None,
        "accounts_receivable_vs_revenue": None,
        "dividend_sustainability": None,
        "performance_metrics": None,
    }
    try:
        t = yf.Ticker(ticker)
        if freq.lower() == "quarterly":
            bs, cf, inc = t.quarterly_balance_sheet, t.quarterly_cashflow, t.quarterly_income_stmt
        else:
            bs, cf, inc = t.balance_sheet, t.cashflow, t.income_stmt
    except Exception as e:
        return {**empty_resp, "error": str(e)}
    if inc.empty and bs.empty and cf.empty:
        return {**empty_resp, "error": "No financial statement data"}
    periods = _periods_from_df(inc) if not inc.empty else _periods_from_df(bs) if not bs.empty else _periods_from_df(cf)
    if not periods:
        return {**empty_resp, "error": "No periods"}
    rev_row = _find_row(inc, "Total Revenue", "Operating Revenue", "Revenue")
    op_inc_row = _find_row(inc, "Total Operating Income As Reported", "Operating Income", "EBIT")
    eps_row = _find_row(inc, "Diluted EPS", "Basic EPS")
    revenue = _align_series_to_periods(periods, inc, rev_row) if rev_row else [None] * len(periods)
    operating_income = _align_series_to_periods(periods, inc, op_inc_row) if op_inc_row else [None] * len(periods)
    eps = _align_series_to_periods(periods, inc, eps_row) if eps_row else [None] * len(periods)
    historical_financials = {"periods": periods, "revenue": revenue, "operating_income": operating_income, "eps": eps}
    shares_row = _find_row(bs, "Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding")
    if not shares_row and not inc.empty:
        shares_row = _find_row(inc, "Diluted Average Shares", "Basic Average Shares")
    shares_vals = _align_series_to_periods(periods, bs, shares_row) if shares_row and bs is not None and not bs.empty else (_align_series_to_periods(periods, inc, shares_row) if shares_row and inc is not None and not inc.empty else [None] * len(periods))
    shares_outstanding = {"periods": periods, "values": shares_vals}
    ltd_row = _find_row(bs, "Long Term Debt And Capital Lease Obligation", "Long Term Debt", "Total Debt")
    fcf_row = _find_row(cf, "Free Cash Flow")
    ltd_vals = _align_series_to_periods(periods, bs, ltd_row) if ltd_row else [None] * len(periods)
    fcf_vals = _align_series_to_periods(periods, cf, fcf_row) if fcf_row else [None] * len(periods)
    long_term_debt_vs_fcf = {"periods": periods, "long_term_debt": ltd_vals, "free_cash_flow": fcf_vals}
    re_row = _find_row(bs, "Retained Earnings")
    re_vals = _align_series_to_periods(periods, bs, re_row) if re_row else [None] * len(periods)
    retained_earnings = {"periods": periods, "values": re_vals}
    cash_row = _find_row(bs, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
    cash_vals = _align_series_to_periods(periods, bs, cash_row) if cash_row else [None] * len(periods)
    total_cash_vs_long_term_debt = {"periods": periods, "total_cash": cash_vals, "long_term_debt": ltd_vals}
    ar_row = _find_row(bs, "Accounts Receivable", "Receivables", "Current Net Receivables")
    ar_vals = _align_series_to_periods(periods, bs, ar_row) if ar_row else [None] * len(periods)
    rev_vals = _align_series_to_periods(periods, inc, rev_row) if rev_row else [None] * len(periods)
    accounts_receivable_vs_revenue = {"periods": periods, "accounts_receivable": ar_vals, "revenue": rev_vals}
    div_row = _find_row(cf, "Cash Dividends Paid", "Common Stock Dividend Paid", "Dividend Payout")
    div_vals = _align_series_to_periods(periods, cf, div_row) if div_row else [None] * len(periods)
    dividend_sustainability = {"periods": periods, "dividends_paid": div_vals, "free_cash_flow": fcf_vals}
    gross_row = _find_row(inc, "Gross Profit")
    pretax_row = _find_row(inc, "Pretax Income", "Tax Provision")
    net_income_row = _find_row(inc, "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest", "Net Income")
    gross_vals = _align_series_to_periods(periods, inc, gross_row) if gross_row else [None] * len(periods)
    pretax_vals = _align_series_to_periods(periods, inc, pretax_row) if pretax_row else [None] * len(periods)
    invested_row = _find_row(bs, "Invested Capital", "Total Capitalization")
    invested_vals = _align_series_to_periods(periods, bs, invested_row) if invested_row else [None] * len(periods)
    ni_vals = _align_series_to_periods(periods, inc, net_income_row) if net_income_row else [None] * len(periods)
    gross_pct = [round(100 * g / r, 2) if r and g and r != 0 else None for g, r in zip(gross_vals, rev_vals)]
    pretax_pct = [round(100 * p / r, 2) if r and p and r != 0 else None for p, r in zip(pretax_vals, rev_vals)]
    roic_pct = [round(100 * ni / inv, 2) if inv and ni and inv != 0 else None for ni, inv in zip(ni_vals, invested_vals)]
    performance_metrics = {"periods": periods, "gross_margin_pct": gross_pct, "pretax_margin_pct": pretax_pct, "roic_pct": roic_pct}
    return {
        "ticker": ticker,
        "frequency": freq,
        "historical_financials": historical_financials,
        "shares_outstanding": shares_outstanding,
        "long_term_debt_vs_fcf": long_term_debt_vs_fcf,
        "retained_earnings": retained_earnings,
        "total_cash_vs_long_term_debt": total_cash_vs_long_term_debt,
        "accounts_receivable_vs_revenue": accounts_receivable_vs_revenue,
        "dividend_sustainability": dividend_sustainability,
        "performance_metrics": performance_metrics,
    }

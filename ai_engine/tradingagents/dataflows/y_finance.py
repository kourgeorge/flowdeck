from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance as yf
import pandas as pd
import os
import glob

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
    Fetches data once and calculates indicator for all available dates.
    Returns dict mapping date strings to indicator values.
    """
    from .config import get_config
    import pandas as pd
    from stockstats import wrap
    import os
    
    def _load_csv_if_valid(path: str) -> pd.DataFrame | None:
        """Return DataFrame only when cache exists, has rows, and includes Date."""
        if not os.path.exists(path):
            return None
        try:
            cached_df = pd.read_csv(path)
            if cached_df.empty or "Date" not in cached_df.columns:
                return None
            cached_df["Date"] = pd.to_datetime(cached_df["Date"], errors="coerce")
            cached_df = cached_df.dropna(subset=["Date"])
            if cached_df.empty:
                return None
            return cached_df
        except Exception:
            return None

    def _latest_valid_symbol_cache(cache_dir: str, ticker: str) -> pd.DataFrame | None:
        pattern = os.path.join(cache_dir, f"{ticker}-YFin-data-*.csv")
        for candidate in sorted(glob.glob(pattern), reverse=True):
            cached_df = _load_csv_if_valid(candidate)
            if cached_df is not None:
                return cached_df
        return None

    config = get_config()
    online = config["data_vendors"]["technical_indicators"] != "local"
    
    if not online:
        # Local data path
        try:
            data = pd.read_csv(
                os.path.join(
                    config.get("data_cache_dir", "data"),
                    f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                )
            )
            df = wrap(data)
        except FileNotFoundError:
            raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
    else:
        # Online data fetching with caching
        today_date = pd.Timestamp.today()
        end_date = today_date
        start_date = today_date - pd.DateOffset(years=15)
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        os.makedirs(config["data_cache_dir"], exist_ok=True)
        
        data_file = os.path.join(
            config["data_cache_dir"],
            f"{symbol}-YFin-data-{start_date_str}-{end_date_str}.csv",
        )
        
        # Prefer today's cache, but ignore corrupt/empty files.
        data = _load_csv_if_valid(data_file)

        if data is None:
            try:
                downloaded = yf.download(
                    symbol,
                    start=start_date_str,
                    end=end_date_str,
                    multi_level_index=False,
                    progress=False,
                    auto_adjust=True,
                ).reset_index()
                if not downloaded.empty and "Date" in downloaded.columns:
                    downloaded["Date"] = pd.to_datetime(downloaded["Date"], errors="coerce")
                    downloaded = downloaded.dropna(subset=["Date"])
                    if not downloaded.empty:
                        downloaded.to_csv(data_file, index=False)
                        data = downloaded
            except Exception:
                data = None

        # Network can fail in offline/sandbox mode; use latest good cache instead.
        if data is None or data.empty:
            fallback_data = _latest_valid_symbol_cache(config["data_cache_dir"], symbol)
            if fallback_data is not None:
                data = fallback_data
            else:
                raise Exception(
                    f"Stockstats fail: no valid cached YFinance data available for {symbol}"
                )
        
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
    """Get insider transactions data from yfinance."""
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        data = ticker_obj.insider_transactions
        
        if data is None or data.empty:
            return f"No insider transactions data found for symbol '{ticker}'"
            
        # Convert to CSV string for consistency with other functions
        csv_string = data.to_csv()
        
        # Add header information
        header = f"# Insider Transactions data for {ticker.upper()}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        return header + csv_string
        
    except Exception as e:
        return f"Error retrieving insider transactions for {ticker}: {str(e)}"


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
        
        # Sort by date (most recent first) - yfinance recommendations are typically already sorted
        # but we'll ensure we get the most recent
        if isinstance(recommendations.index, pd.DatetimeIndex):
            recommendations = recommendations.sort_index(ascending=False)
        
        # Get the most recent recommendation row (first row after sorting)
        latest_row = recommendations.iloc[0]
        
        # Extract recommendation counts
        breakdown = {}
        total = 0
        recommendation_columns = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']
        
        for col in recommendation_columns:
            if col in latest_row.index:
                count = int(latest_row[col]) if pd.notna(latest_row[col]) else 0
                breakdown[col] = count
                total += count
        
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
        
        # Get target price from info
        info = ticker_obj.info
        target_price = info.get('targetMeanPrice') or info.get('targetHighPrice') or info.get('targetLowPrice')
        
        # Get latest date
        latest_date = None
        if not recommendations.empty:
            latest_index = recommendations.index[0]
            if hasattr(latest_index, 'strftime'):
                latest_date = latest_index.strftime("%Y-%m-%d")
            else:
                latest_date = str(latest_index)
        
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

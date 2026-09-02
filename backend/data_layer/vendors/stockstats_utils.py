import io

import pandas as pd
import yfinance as yf
from stockstats import wrap
from typing import Annotated

from services.data_cache import get_cached, get_cached_raw
from config import DATA_CACHE_TTL_VENDOR_OHLCV
from .yf_session import get_yf_session


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        cache_key = f"vendor_ohlcv:{symbol.upper()}"

        def _fetch_ohlcv() -> str:
            today_date = pd.Timestamp.today()
            end_date = today_date
            start_date = (today_date - pd.DateOffset(years=15)).strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            try:
                downloaded = yf.download(
                    symbol,
                    start=start_date,
                    end=end_date_str,
                    multi_level_index=False,
                    progress=False,
                    auto_adjust=True,
                    session=get_yf_session(),
                ).reset_index()
                if downloaded.empty or "Date" not in downloaded.columns:
                    raise ValueError("Empty or invalid download")
                downloaded["Date"] = pd.to_datetime(downloaded["Date"], errors="coerce")
                downloaded = downloaded.dropna(subset=["Date"])
                if downloaded.empty:
                    raise ValueError("No valid rows")
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

        df[indicator]  # trigger stockstats to calculate the indicator
        curr_date_str = curr_date if isinstance(curr_date, str) else pd.to_datetime(curr_date).strftime("%Y-%m-%d")
        matching_rows = df[df["Date"].astype(str).str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"

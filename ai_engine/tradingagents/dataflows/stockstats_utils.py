import pandas as pd
import yfinance as yf
from stockstats import wrap
from typing import Annotated
import os
import glob
from .config import get_config, DATA_DIR


class StockstatsUtils:
    @staticmethod
    def _load_csv_if_valid(path: str):
        """Return DataFrame only when cache exists, has rows, and includes Date."""
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            if df.empty or "Date" not in df.columns:
                return None
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.dropna(subset=["Date"])
            if df.empty:
                return None
            return df
        except Exception:
            return None

    @staticmethod
    def _latest_valid_symbol_cache(cache_dir: str, symbol: str):
        pattern = os.path.join(cache_dir, f"{symbol}-YFin-data-*.csv")
        for candidate in sorted(glob.glob(pattern), reverse=True):
            df = StockstatsUtils._load_csv_if_valid(candidate)
            if df is not None:
                return df
        return None

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
        # Get config and set up data directory path
        config = get_config()
        online = config["data_vendors"]["technical_indicators"] != "local"

        df = None
        data = None

        if not online:
            try:
                data = pd.read_csv(
                    os.path.join(
                        DATA_DIR,
                        f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                    )
                )
                df = wrap(data)
            except FileNotFoundError:
                raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
        else:
            # Get today's date as YYYY-mm-dd to add to cache
            today_date = pd.Timestamp.today()
            curr_date = pd.to_datetime(curr_date)

            end_date = today_date
            start_date = today_date - pd.DateOffset(years=15)
            start_date = start_date.strftime("%Y-%m-%d")
            end_date = end_date.strftime("%Y-%m-%d")

            # Get config and ensure cache directory exists
            os.makedirs(config["data_cache_dir"], exist_ok=True)

            data_file = os.path.join(
                config["data_cache_dir"],
                f"{symbol}-YFin-data-{start_date}-{end_date}.csv",
            )

            data = StockstatsUtils._load_csv_if_valid(data_file)

            if data is None:
                try:
                    downloaded = yf.download(
                        symbol,
                        start=start_date,
                        end=end_date,
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

            if data is None or data.empty:
                data = StockstatsUtils._latest_valid_symbol_cache(config["data_cache_dir"], symbol)
                if data is None:
                    raise Exception(f"Stockstats fail: no valid cached YFinance data available for {symbol}")

            df = wrap(data)
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            curr_date = curr_date.strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"

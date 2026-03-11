"""
Information Fetcher Engine: single entry point for all market/data fetching.

- News: app news API only (services/news_fetcher → Yahoo). Same data for UI and agents.
- Other data: yfinance in-engine or tradingagents where needed.
Used by both the dashboard HTTP API and (via info service client) by AI agents.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import date, datetime, timedelta
import numbers
from pathlib import Path
from typing import Any, Dict, List, Optional

def _default_company_info(symbol: str, quote_type: Any = None) -> Dict[str, Any]:
    """Return a minimal company info dict when fetch fails."""
    if quote_type is None and symbol.startswith("^"):
        quote_type = "INDEX"
    return {
        "name": symbol,
        "sector": "N/A",
        "industry": "N/A",
        "exchange": "N/A",
        "country": "N/A",
        "website": "N/A",
        "quoteType": quote_type,
    }


# Lazy tradingagents import to avoid hard dependency at import time
def _tradingagents_route_to_vendor():
    import sys
    backend_dir = Path(__file__).resolve().parent.parent
    tradingagents_dir = backend_dir.parent  # repo root (backend is at root)
    if str(tradingagents_dir) not in sys.path:
        sys.path.insert(0, str(tradingagents_dir))
    from ai_engine.tradingagents.dataflows.interface import route_to_vendor
    return route_to_vendor


class InfoFetcher:
    """
    Central engine to fetch information from different sources.
    All methods return dicts/lists suitable for JSON API responses.
    """

    def __init__(
        self,
        market_data_service: Optional[Any] = None,
        news_service: Optional[Any] = None,
    ):
        self._market_data_service = market_data_service
        self._news_service = news_service
        self._route_to_vendor = None
        # In-memory cache for sector/industry data (loaded from JSON file)
        self._sector_cache: Dict[str, Dict[str, Any]] = {}
        self._sector_cache_lock = threading.Lock()
        
        # Load major stocks sector/industry data from JSON file
        self._load_major_tickers_sectors()

    def _get_route_to_vendor(self):
        if self._route_to_vendor is None:
            self._route_to_vendor = _tradingagents_route_to_vendor()
        return self._route_to_vendor

    def _get_market_data_service(self):
        if self._market_data_service is None:
            from services.market_data_service import MarketDataService
            self._market_data_service = MarketDataService()
        return self._market_data_service

    def _get_news_service(self):
        if self._news_service is None:
            from services.news_service import NewsService
            self._news_service = NewsService()
        return self._news_service

    # ---------- Quote & market ----------
    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get current market quote for a ticker."""
        ticker = ticker.upper()
        svc = self._get_market_data_service()
        quote = svc.get_current_quote(ticker)
        if quote is None:
            return None
        return quote.model_dump() if hasattr(quote, "model_dump") else quote.dict()

    def get_historical(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
    ) -> Dict[str, Any]:
        """Get historical OHLCV data. Uses yfinance in-engine; can be overridden.
        When period=1d and interval is intraday (1m, 2m, 5m, 15m, 30m, 60m), returns
        the last trading day's intraday data (not today's partial day)."""
        import yfinance as yf
        ticker = ticker.upper()
        ticker_obj = yf.Ticker(ticker)
        intraday_intervals = ("1m", "2m", "5m", "15m", "30m", "60m")
        use_last_trading_day = period == "1d" and interval in intraday_intervals
        if use_last_trading_day:
            today = date.today()
            if today.weekday() == 0:  # Monday -> last trading day is Friday
                last_close = today - timedelta(days=3)
            else:
                last_close = today - timedelta(days=1)
            start = last_close.strftime("%Y-%m-%d")
            end = (last_close + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = ticker_obj.history(start=start, end=end, interval=interval)
        else:
            hist = ticker_obj.history(period=period, interval=interval)
        if hist.empty:
            return {"ticker": ticker, "period": period, "interval": interval, "data": [], "count": 0}
        data = []
        for date_idx, row in hist.iterrows():
            d = date_idx
            if hasattr(d, "tz_localize") and d.tzinfo is not None:
                d = d.tz_localize(None)
            if use_last_trading_day and hasattr(d, "strftime"):
                date_str = d.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            adj_close = row.get("Close")
            if "Adj Close" in row:
                adj_close = row["Adj Close"]
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

    # ---------- News ----------
    def get_news(
        self,
        ticker: str,
        vendor: Optional[str] = None,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        """Get news articles for a ticker."""
        ticker = ticker.upper()
        svc = self._get_news_service()
        return svc.get_news(ticker, vendor=vendor or "yfinance", lookback_days=lookback_days)

    def get_insider_transactions(
        self,
        ticker: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get latest insider transactions from Yahoo Finance."""
        import yfinance as yf
        import pandas as pd

        ticker = ticker.upper()
        curr_date = datetime.now().strftime("%Y-%m-%d")

        try:
            raw_df = yf.Ticker(ticker).insider_transactions
        except Exception as e:
            return {
                "ticker": ticker,
                "date": curr_date,
                "transactions": [],
                "count": 0,
                "error": str(e),
            }

        if raw_df is None or raw_df.empty:
            return {
                "ticker": ticker,
                "date": curr_date,
                "transactions": [],
                "count": 0,
            }

        df = raw_df.copy()
        if "Start Date" in df.columns:
            df = df.sort_values(by="Start Date", ascending=False, na_position="last")
        if limit > 0:
            df = df.head(limit)

        def _cell(row: Dict[str, Any], key: str) -> Any:
            val = row.get(key)
            if pd.isna(val):
                return None
            # Convert pandas timestamps and numpy scalars to JSON-serializable values.
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

        transactions: List[Dict[str, Any]] = []
        for row in df.to_dict(orient="records"):
            transactions.append(
                {
                    "insider": _cell(row, "Insider"),
                    "position": _cell(row, "Position"),
                    "transaction": _cell(row, "Transaction"),
                    "start_date": _cell(row, "Start Date"),
                    "shares": _cell(row, "Shares"),
                    "value": _cell(row, "Value"),
                    "ownership": _cell(row, "Ownership"),
                    "url": _cell(row, "URL"),
                    "text": _cell(row, "Text"),
                }
            )

        return {
            "ticker": ticker,
            "date": curr_date,
            "transactions": transactions,
            "count": len(transactions),
        }

    # ---------- Company & fundamentals ----------
    def get_company_info_batch(self, tickers: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get company profile (name, sector, industry, etc.) for multiple tickers in one batch via yahooquery."""
        if not tickers:
            return {}
        symbols = [t.upper() for t in tickers]
        try:
            from yahooquery import Ticker as YahooQueryTicker
        except Exception:
            return {}
        try:
            ticker_obj = YahooQueryTicker(symbols)
        except Exception:
            return {}
        try:
            raw = ticker_obj.get_modules("price quoteType summaryProfile")
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        for symbol in symbols:
            per = raw.get(symbol) or raw.get(symbol.upper()) or raw.get(symbol.lower())
            if not isinstance(per, dict):
                result[symbol] = _default_company_info(symbol)
                continue
            price = per.get("price") if isinstance(per.get("price"), dict) else {}
            quote_type = per.get("quoteType") if isinstance(per.get("quoteType"), dict) else {}
            profile = per.get("summaryProfile") if isinstance(per.get("summaryProfile"), dict) else {}
            name = (price or {}).get("longName") or (price or {}).get("shortName") or (profile or {}).get("longName") or (profile or {}).get("shortName") or symbol
            qt = (quote_type or price or {}).get("quoteType")
            if qt is None and symbol.startswith("^"):
                qt = "INDEX"
            result[symbol] = {
                "name": name,
                "sector": (profile or {}).get("sector") or "N/A",
                "industry": (profile or {}).get("industry") or "N/A",
                "exchange": (quote_type or {}).get("exchange") or "N/A",
                "country": (profile or {}).get("country") or "N/A",
                "website": (profile or {}).get("website") or "N/A",
                "quoteType": qt,
            }
        return result

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """Get company profile (name, sector, industry, etc.)."""
        ticker = ticker.upper()
        batch = self.get_company_info_batch([ticker])
        if ticker in batch:
            return batch[ticker]
        import yfinance as yf
        try:
            info = yf.Ticker(ticker).info
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
            quote_type = "INDEX" if ticker.startswith("^") else None
            return _default_company_info(ticker, quote_type=quote_type)

    def get_extended_info(self, ticker: str) -> Dict[str, Any]:
        """Get extended metrics (beta, market cap, margins, etc.)."""
        import yfinance as yf
        ticker = ticker.upper()
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            try:
                hist = ticker_obj.history(period="3mo")
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
            return {
                "beta": None, "market_cap": None, "revenue": None, "gross_margin": None,
                "dividend_yield": None, "trailing_eps": None, "forward_eps": None,
                "average_volume": None, "enterprise_value": None, "profit_margin": None,
                "operating_margin": None, "ebitda": None, "pe_ratio": None, "forward_pe": None,
            }

    def get_fundamentals(self, ticker: str) -> Dict[str, Any]:
        """Get fundamental data (from tradingagents yfinance)."""
        ticker = ticker.upper()
        curr_date = datetime.now().strftime("%Y-%m-%d")
        try:
            _tradingagents_route_to_vendor()  # ensure path
            from ai_engine.tradingagents.dataflows.y_finance import get_fundamentals_core
            fundamentals_data = get_fundamentals_core(ticker, curr_date)
        except Exception as e:
            return {"ticker": ticker, "date": curr_date, "fundamentals": {}, "error": str(e)}
        return {"ticker": ticker, "date": curr_date, "fundamentals": fundamentals_data}

    def get_financial_statements(
        self,
        ticker: str,
        statement_type: str = "all",
        freq: str = "quarterly",
    ) -> Dict[str, Any]:
        """Get balance sheet, cashflow, income statement from app service (Yahoo Finance). Same data as UI."""
        from services.financial_statements_service import get_financial_statements as get_statements
        return get_statements(ticker, statement_type=statement_type, freq=freq)

    def get_ticker_data(self, ticker: str, start_date: str, end_date: str) -> str:
        """Get OHLCV time series as string (for agents). Uses tradingagents route_to_vendor."""
        route = self._get_route_to_vendor()
        return route("get_ticker_data", ticker.upper(), start_date, end_date)

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        """Get chart-ready time series for fundamentals (Revenue, EPS, Debt, FCF, etc.)."""
        from services.financial_charts_service import get_financial_charts as get_charts
        return get_charts(ticker.upper(), freq=freq)

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get analyst recommendations from yahooquery."""
        try:
            from yahooquery import Ticker as YahooQueryTicker
            import pandas as pd

            ticker_upper = ticker.upper()
            ticker_obj = YahooQueryTicker(ticker_upper)

            def _safe_int(value: Any) -> int:
                try:
                    if value is None:
                        return 0
                    if isinstance(value, bool):
                        return 0
                    if isinstance(value, (int, float)):
                        return int(value)
                    return int(float(str(value)))
                except Exception:
                    return 0

            def _safe_optional_int(value: Any) -> Optional[int]:
                try:
                    if value is None:
                        return None
                    if isinstance(value, bool):
                        return None
                    if isinstance(value, (int, float)):
                        return int(value)
                    return int(float(str(value)))
                except Exception:
                    return None

            def _normalize_trend_row(row: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "period": str(row.get("period") or ""),
                    "strongBuy": _safe_int(row.get("strongBuy")),
                    "buy": _safe_int(row.get("buy")),
                    "hold": _safe_int(row.get("hold")),
                    "sell": _safe_int(row.get("sell")),
                    "strongSell": _safe_int(row.get("strongSell")),
                }

            def _extract_trend_rows(raw: Any) -> List[Dict[str, Any]]:
                if raw is None:
                    return []
                if isinstance(raw, dict):
                    candidate = raw.get(ticker_upper)
                    if candidate is None:
                        for key, value in raw.items():
                            if str(key).upper() == ticker_upper:
                                candidate = value
                                break
                    if isinstance(candidate, dict):
                        if candidate.get("error"):
                            return []
                        return [_normalize_trend_row(candidate)]
                    if isinstance(candidate, list):
                        rows = [r for r in candidate if isinstance(r, dict)]
                        return [_normalize_trend_row(r) for r in rows]
                    row_keys = {"period", "strongBuy", "buy", "hold", "sell", "strongSell"}
                    # Fallback only when dictionary is row-like (not a symbol-keyed map we failed to match).
                    if row_keys.intersection(raw.keys()):
                        return [_normalize_trend_row(raw)]
                    return []
                if isinstance(raw, list):
                    rows = [r for r in raw if isinstance(r, dict)]
                    return [_normalize_trend_row(r) for r in rows]
                if isinstance(raw, pd.DataFrame):
                    if raw.empty:
                        return []
                    rows: List[Dict[str, Any]] = []
                    for _, r in raw.iterrows():
                        try:
                            rows.append(_normalize_trend_row(r.to_dict()))
                        except Exception:
                            continue
                    return rows
                return []

            def _extract_latest_row(raw: Any) -> Optional[Dict[str, Any]]:
                if raw is None:
                    return None
                trend_rows = _extract_trend_rows(raw)
                if not trend_rows:
                    return None
                zero_month_row = next((r for r in trend_rows if r.get("period") == "0m"), None)
                return zero_month_row or trend_rows[0]

            trend_raw = getattr(ticker_obj, "recommendation_trend", None)
            trend_rows = _extract_trend_rows(trend_raw)
            trend_row = _extract_latest_row(trend_raw)

            strong_buy = _safe_int((trend_row or {}).get("strongBuy"))
            buy = _safe_int((trend_row or {}).get("buy"))
            hold = _safe_int((trend_row or {}).get("hold"))
            sell = _safe_int((trend_row or {}).get("sell"))
            strong_sell = _safe_int((trend_row or {}).get("strongSell"))

            breakdown = {
                "Strong Buy": strong_buy,
                "Buy": buy,
                "Hold": hold,
                "Sell": sell,
                "Strong Sell": strong_sell,
            }
            trend_total = strong_buy + buy + hold + sell + strong_sell

            recommendation: Optional[str] = None
            if trend_total > 0:
                buy_score = strong_buy + buy
                sell_score = sell + strong_sell
                hold_score = hold
                best = max(buy_score, sell_score, hold_score)
                if best == buy_score:
                    recommendation = "BUY"
                elif best == sell_score:
                    recommendation = "SELL"
                else:
                    recommendation = "HOLD"

            financial_data_raw = getattr(ticker_obj, "financial_data", None)
            financial_data_map = self._get_symbol_payload(financial_data_raw, ticker_upper)
            if not isinstance(financial_data_map, dict):
                financial_data_map = {}

            current_price = self._coerce_float(financial_data_map.get("currentPrice"))
            target_price = self._coerce_float(financial_data_map.get("targetMeanPrice"))
            target_low_price = self._coerce_float(financial_data_map.get("targetLowPrice"))
            target_high_price = self._coerce_float(financial_data_map.get("targetHighPrice"))
            target_median_price = self._coerce_float(financial_data_map.get("targetMedianPrice"))
            recommendation_mean = self._coerce_float(financial_data_map.get("recommendationMean"))
            number_of_analyst_opinions = _safe_optional_int(
                financial_data_map.get("numberOfAnalystOpinions")
            )
            max_age = _safe_optional_int(financial_data_map.get("maxAge"))

            total = (
                number_of_analyst_opinions
                if isinstance(number_of_analyst_opinions, int) and number_of_analyst_opinions > 0
                else trend_total
            )

            recommendation_key_raw = financial_data_map.get("recommendationKey")
            recommendation_key = str(recommendation_key_raw or "").strip().lower()
            if recommendation is None:
                if recommendation_key in ("strong_buy", "buy"):
                    recommendation = "BUY"
                elif recommendation_key in ("strong_sell", "sell"):
                    recommendation = "SELL"
                elif recommendation_key == "hold":
                    recommendation = "HOLD"

            return {
                "ticker": ticker_upper,
                "recommendation": recommendation,
                "target_price": target_price,
                "breakdown": breakdown,
                "total_analysts": total,
                # recommendation_trend payload is period-relative and usually has no true date field
                "latest_date": None,
                "recommendation_trend": trend_rows,
                "price_targets": {
                    "current": current_price,
                    "average": target_price,
                    "low": target_low_price,
                    "high": target_high_price,
                },
                "financial_data": {
                    "maxAge": max_age,
                    "currentPrice": current_price,
                    "targetHighPrice": target_high_price,
                    "targetLowPrice": target_low_price,
                    "targetMeanPrice": target_price,
                    "targetMedianPrice": target_median_price,
                    "recommendationMean": recommendation_mean,
                    "recommendationKey": (
                        str(recommendation_key_raw).strip() if recommendation_key_raw is not None else None
                    ),
                    "numberOfAnalystOpinions": number_of_analyst_opinions,
                },
            }
        except Exception:
            raise

    def get_future_events(self, ticker: str) -> Dict[str, Any]:
        """Get upcoming earnings and ex-dividend dates from Yahoo Finance (yfinance)."""
        import yfinance as yf
        ticker = ticker.upper()
        today = datetime.now().date()
        events: List[Dict[str, Any]] = []
        try:
            t = yf.Ticker(ticker)
            info = t.info
            if info is None:
                info = {}
            # Next ex-dividend date (Unix timestamp; only include if in the future)
            ex_ts = info.get("exDividendDate")
            if ex_ts is not None:
                try:
                    from datetime import timezone
                    ex_date = datetime.fromtimestamp(ex_ts, tz=timezone.utc).date()
                except Exception:
                    ex_date = datetime.fromtimestamp(ex_ts).date()
                if ex_date >= today:
                    events.append({
                        "date": ex_date.strftime("%Y-%m-%d"),
                        "type": "ex_dividend",
                        "label": "Ex-dividend date",
                    })
            # Earnings dates (DataFrame: index = date, optional columns like EPS Estimate)
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
                        eps_estimate_val = None
                        if eps_est is not None:
                            try:
                                fval = float(eps_est)
                                if not math.isnan(fval):
                                    eps_estimate_val = fval
                                    label = f"Earnings (EPS est. ${fval:.2f})"
                            except (TypeError, ValueError):
                                pass
                        events.append({
                            "date": date_str,
                            "type": "earnings",
                            "label": label,
                            "eps_estimate": eps_estimate_val,
                        })
            except Exception:
                pass
            # Optional: calendar dict (Yahoo sometimes has Earnings/Dividend keys)
            try:
                cal = t.calendar
                if isinstance(cal, dict):
                    for key in ("Earnings", "Earnings Date", "Dividend Date"):
                        val = cal.get(key)
                        if val is None:
                            continue
                        if isinstance(val, (int, float)):
                            try:
                                from datetime import timezone
                                dt = datetime.fromtimestamp(val, tz=timezone.utc).date()
                            except Exception:
                                dt = datetime.fromtimestamp(val).date()
                            if dt >= today and not any(e.get("date") == dt.strftime("%Y-%m-%d") and e.get("type") == ("ex_dividend" if "Dividend" in key else "earnings") for e in events):
                                events.append({
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "type": "ex_dividend" if "Dividend" in key else "earnings",
                                    "label": "Ex-dividend date" if "Dividend" in key else "Earnings",
                                })
            except Exception:
                pass
            # Dedupe by (date, type) and sort by date
            seen = set()
            unique: List[Dict[str, Any]] = []
            for e in sorted(events, key=lambda x: x["date"]):
                k = (e["date"], e["type"])
                if k not in seen:
                    seen.add(k)
                    unique.append(e)
            return {"ticker": ticker, "events": unique, "count": len(unique)}
        except Exception as e:
            return {"ticker": ticker, "events": [], "count": 0, "error": str(e)}

    def get_fund_info(self, ticker: str) -> Dict[str, Any]:
        """Get ETF/fund-specific data (AUM, expense ratio, category, holdings, sector weightings, etc.)."""
        import yfinance as yf
        ticker = ticker.upper()
        out: Dict[str, Any] = {
            "ticker": ticker,
            "totalAssets": None,
            "yield": None,
            "category": None,
            "fundInception": None,
            "expenseRatio": None,
            "description": None,
            "fund_overview": None,
            "top_holdings": None,
            "sector_weightings": None,
            "asset_classes": None,
        }
        try:
            t = yf.Ticker(ticker)
            info = t.info
            # From ticker.info (Yahoo often has these for ETFs)
            out["totalAssets"] = info.get("totalAssets")
            out["yield"] = info.get("yield")
            out["category"] = info.get("category")
            out["fundInception"] = info.get("fundInception")
            out["expenseRatio"] = info.get("expenseRatio")
            # funds_data (top holdings, sector weightings, etc.)
            try:
                fd = t.funds_data
                if fd is not None:
                    out["description"] = getattr(fd, "description", None)
                    out["fund_overview"] = getattr(fd, "fund_overview", None)
                    # DataFrames -> list of dicts for JSON
                    th = getattr(fd, "top_holdings", None)
                    if th is not None and hasattr(th, "to_dict"):
                        out["top_holdings"] = th.to_dict(orient="records")
                    # Dicts (sector_weightings, asset_classes) are JSON-serializable
                    out["sector_weightings"] = getattr(fd, "sector_weightings", None)
                    out["asset_classes"] = getattr(fd, "asset_classes", None)
            except Exception:
                pass
            return out
        except Exception:
            return out
    def _load_major_tickers_sectors(self):
        """Load major tickers sector/industry data from JSON file.
        
        Loads pre-generated sector/industry data from backend/data/major_stocks_sectors.json
        into the cache. This avoids API rate limits and provides instant lookups.
        
        If the file doesn't exist, the cache remains empty and data will be fetched
        on-demand when needed.
        """
        data_file = Path(__file__).parent.parent / "data" / "major_stocks_sectors.json"
        self._major_tickers = []

        if not data_file.exists():
            return

        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._sector_cache_lock:
                for ticker, info in data.items():
                    if not info.get("error"):
                        self._sector_cache[ticker] = info

            self._major_tickers = list(data.keys())
        except Exception as e:
            print(f"Warning: Could not load major_stocks_sectors.json: {e}")
    
    def _fetch_sector_info_batch_yahooquery(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch sector/industry and related info for multiple tickers in one batch via yahooquery.
        
        Uses get_modules() so a single HTTP request fetches all needed data (price, summaryProfile,
        summaryDetail, financialData, defaultKeyStatistics). Returns a dict symbol -> sector_info.
        Does not modify cache; caller should merge into _sector_cache.
        """
        if not symbols:
            return {}
        symbols = [s.upper() for s in symbols]
        try:
            from yahooquery import Ticker as YahooQueryTicker
        except Exception:
            return {}

        try:
            ticker_obj = YahooQueryTicker(symbols)
        except Exception:
            return {}

        # Single request for all modules (avoids 5 round-trips and reduces UI delay).
        modules = "price summaryProfile summaryDetail financialData defaultKeyStatistics"
        try:
            raw = ticker_obj.get_modules(modules)
        except Exception:
            raw = {}

        if not isinstance(raw, dict):
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for symbol in symbols:
            per_symbol = raw.get(symbol) or raw.get(symbol.upper()) or raw.get(symbol.lower())
            if not isinstance(per_symbol, dict):
                continue
            price = per_symbol.get("price") if isinstance(per_symbol.get("price"), dict) else {}
            profile = per_symbol.get("summaryProfile") if isinstance(per_symbol.get("summaryProfile"), dict) else {}
            detail = per_symbol.get("summaryDetail") if isinstance(per_symbol.get("summaryDetail"), dict) else {}
            financial = per_symbol.get("financialData") if isinstance(per_symbol.get("financialData"), dict) else {}
            key_stats = per_symbol.get("defaultKeyStatistics") if isinstance(per_symbol.get("defaultKeyStatistics"), dict) else {}

            if not profile and not price:
                continue

            name = (price or {}).get("longName") or (price or {}).get("shortName") or (profile or {}).get("longName") or (profile or {}).get("shortName") or symbol

            sector_info = {
                "name": name,
                "sector": (profile or {}).get("sector"),
                "industry": (profile or {}).get("industry"),
                "market_cap": self._coerce_float((detail or price or {}).get("marketCap") or (price or {}).get("marketCap")),
                "quote_type": (price or {}).get("quoteType"),
                "trailing_pe": self._coerce_float((detail or {}).get("trailingPE")),
                "forward_pe": self._coerce_float((detail or {}).get("forwardPE")),
                "trailing_eps": self._coerce_float((key_stats or {}).get("trailingEps")),
                "forward_eps": self._coerce_float((key_stats or {}).get("forwardEps")),
                "ebitda": self._coerce_float((financial or {}).get("ebitda")),
                "revenue": self._coerce_float((financial or {}).get("totalRevenue")),
                "profit_margin": self._coerce_float((financial or {}).get("profitMargins")),
                "gross_margin": self._coerce_float((financial or {}).get("grossMargins")),
                "operating_margin": self._coerce_float((financial or {}).get("operatingMargins")),
                "ebitda_margin": self._coerce_float((financial or {}).get("ebitdaMargins")),
                "beta": self._coerce_float((detail or key_stats or {}).get("beta")),
                "dividend_yield": self._coerce_float((detail or {}).get("dividendYield")),
                "fifty_two_week_high": self._coerce_float((detail or price or {}).get("fiftyTwoWeekHigh")),
                "fifty_two_week_low": self._coerce_float((detail or price or {}).get("fiftyTwoWeekLow")),
                "target_mean_price": self._coerce_float((financial or {}).get("targetMeanPrice")),
                "recommendation_key": (financial or {}).get("recommendationKey"),
            }
            result[symbol] = sector_info

        return result

    def _fetch_sector_info_yfinance(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fallback: fetch sector/industry info from yfinance when yahooquery fails or returns no data."""
        try:
            import yfinance as yf
        except Exception:
            return None
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            return None
        if not info:
            return None
        sector_info = {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": self._coerce_float(info.get("marketCap")),
            "quote_type": info.get("quoteType"),
            "trailing_pe": self._coerce_float(info.get("trailingPE")),
            "forward_pe": self._coerce_float(info.get("forwardPE")),
            "trailing_eps": self._coerce_float(info.get("trailingEps")),
            "forward_eps": self._coerce_float(info.get("forwardEps")),
            "ebitda": self._coerce_float(info.get("ebitda")),
            "revenue": self._coerce_float(info.get("totalRevenue")),
            "profit_margin": self._coerce_float(info.get("profitMargins")),
            "gross_margin": self._coerce_float(info.get("grossMargins")),
            "operating_margin": self._coerce_float(info.get("operatingMargins")),
            "ebitda_margin": self._coerce_float(info.get("ebitdaMargins")),
            "beta": self._coerce_float(info.get("beta")),
            "dividend_yield": self._coerce_float(info.get("dividendYield")),
            "fifty_two_week_high": self._coerce_float(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": self._coerce_float(info.get("fiftyTwoWeekLow")),
            "target_mean_price": self._coerce_float(info.get("targetMeanPrice")),
            "recommendation_key": info.get("recommendationKey"),
        }
        return sector_info

    def _get_or_fetch_sector_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get sector/industry info from cache or fetch via yahooquery (single or batch).
        
        Falls back to yfinance when yahooquery fails or returns no data.
        """
        ticker = ticker.upper()

        with self._sector_cache_lock:
            if ticker in self._sector_cache:
                return self._sector_cache[ticker]

        batch = self._fetch_sector_info_batch_yahooquery([ticker])
        sector_info = batch.get(ticker)
        if sector_info is None:
            sector_info = self._fetch_sector_info_yfinance(ticker)
        if sector_info is not None:
            with self._sector_cache_lock:
                self._sector_cache[ticker] = sector_info
            return sector_info
        return None

    def get_similar_tickers(
        self,
        ticker: str,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get similar tickers based on sector/industry matching.
        
        Uses prefetched sector/industry data from cache for fast lookups.
        Returns tickers with basic info (no price data for faster performance).
        
        The cache is populated at app startup in a background thread.
        """
        ticker = ticker.upper()
        
        # Get target ticker's sector and industry (from cache or fetch)
        target_info = self._get_or_fetch_sector_info(ticker)
        if not target_info:
            return {
                "ticker": ticker,
                "sector": None,
                "industry": None,
                "similar_tickers": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "error": "Failed to fetch ticker information"
            }
        
        target_sector = target_info.get("sector")
        target_industry = target_info.get("industry")
        target_quote_type = target_info.get("quote_type")
        
        # Skip similar tickers for indices and some other types
        if target_quote_type in ("INDEX", "CURRENCY", "CRYPTOCURRENCY"):
            return {
                "ticker": ticker,
                "sector": target_sector,
                "industry": target_industry,
                "similar_tickers": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "match_type": "not_applicable",
                "message": f"Similar tickers not available for {target_quote_type} type"
            }
        
        if not target_sector and not target_industry:
            return {
                "ticker": ticker,
                "sector": None,
                "industry": None,
                "similar_tickers": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "match_type": "no_data",
                "message": "No sector/industry data available for this ticker"
            }
        
        # Use cached sector/industry matching with batch quote enrichment.
        try:
            return self._get_similar_tickers_cached(
                ticker, target_info, target_sector, target_industry, limit, offset
            )
        except Exception as e:
            return {
                "ticker": ticker,
                "sector": target_sector,
                "industry": target_industry,
                "similar_tickers": [],
                "count": 0,
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "has_more": False,
                "match_type": "error",
                "error": str(e)
            }
    
    
    def _get_similar_tickers_cached(
        self,
        ticker: str,
        target_info: Dict[str, Any],
        target_sector: Optional[str],
        target_industry: Optional[str],
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """Get similar tickers using prefetched sector/industry data for fast matching.
        
        Uses the cached sector/industry data from self._sector_cache. Missing entries
        are fetched in one batch via yahooquery to avoid per-ticker rate limits.
        """
        major_tickers = [t for t in self._major_tickers if t != ticker]

        # Batch-fetch sector info for all candidates not yet in cache (one yahooquery request).
        with self._sector_cache_lock:
            missing = [t for t in major_tickers if t not in self._sector_cache]
        if missing:
            batch_result = self._fetch_sector_info_batch_yahooquery(missing)
            if batch_result:
                with self._sector_cache_lock:
                    for sym, info in batch_result.items():
                        self._sector_cache[sym] = info

        exact_matches: List[Dict[str, Any]] = []
        sector_only_matches: List[Dict[str, Any]] = []

        for candidate_ticker in major_tickers:
            candidate_info = self._get_or_fetch_sector_info(candidate_ticker)
            if not candidate_info:
                continue
            
            candidate_sector = candidate_info.get("sector")
            candidate_industry = candidate_info.get("industry")
            
            sector_match = target_sector and candidate_sector == target_sector
            industry_match = target_industry and candidate_industry == target_industry
            
            if sector_match and industry_match:
                exact_matches.append({
                    "ticker": candidate_ticker,
                    "name": candidate_info.get("name", candidate_ticker),
                    "sector": candidate_sector,
                    "industry": candidate_industry,
                    "market_cap": candidate_info.get("market_cap"),
                    "current_price": None,
                    "change_percent": None,
                    "trailing_pe": candidate_info.get("trailing_pe"),
                    "forward_pe": candidate_info.get("forward_pe"),
                    "trailing_eps": candidate_info.get("trailing_eps"),
                    "forward_eps": candidate_info.get("forward_eps"),
                    "ebitda": candidate_info.get("ebitda"),
                    "revenue": candidate_info.get("revenue"),
                    "profit_margin": candidate_info.get("profit_margin"),
                    "gross_margin": candidate_info.get("gross_margin"),
                    "operating_margin": candidate_info.get("operating_margin"),
                    "ebitda_margin": candidate_info.get("ebitda_margin"),
                    "beta": candidate_info.get("beta"),
                    "dividend_yield": candidate_info.get("dividend_yield"),
                    "fifty_two_week_high": candidate_info.get("fifty_two_week_high"),
                    "fifty_two_week_low": candidate_info.get("fifty_two_week_low"),
                    "target_mean_price": candidate_info.get("target_mean_price"),
                    "recommendation_key": candidate_info.get("recommendation_key"),
                })
            elif sector_match:
                sector_only_matches.append({
                    "ticker": candidate_ticker,
                    "name": candidate_info.get("name", candidate_ticker),
                    "sector": candidate_sector,
                    "industry": candidate_industry,
                    "market_cap": candidate_info.get("market_cap"),
                    "current_price": None,
                    "change_percent": None,
                    "trailing_pe": candidate_info.get("trailing_pe"),
                    "forward_pe": candidate_info.get("forward_pe"),
                    "trailing_eps": candidate_info.get("trailing_eps"),
                    "forward_eps": candidate_info.get("forward_eps"),
                    "ebitda": candidate_info.get("ebitda"),
                    "revenue": candidate_info.get("revenue"),
                    "profit_margin": candidate_info.get("profit_margin"),
                    "gross_margin": candidate_info.get("gross_margin"),
                    "operating_margin": candidate_info.get("operating_margin"),
                    "ebitda_margin": candidate_info.get("ebitda_margin"),
                    "beta": candidate_info.get("beta"),
                    "dividend_yield": candidate_info.get("dividend_yield"),
                    "fifty_two_week_high": candidate_info.get("fifty_two_week_high"),
                    "fifty_two_week_low": candidate_info.get("fifty_two_week_low"),
                    "target_mean_price": candidate_info.get("target_mean_price"),
                    "recommendation_key": candidate_info.get("recommendation_key"),
                })
                
        # Prioritize exact sector+industry matches first, then sector-only matches.
        exact_matches.sort(key=lambda x: x["market_cap"] if x["market_cap"] else 0, reverse=True)
        sector_only_matches.sort(key=lambda x: x["market_cap"] if x["market_cap"] else 0, reverse=True)

        safe_offset = max(0, int(offset))
        safe_limit = max(1, int(limit))

        # Prefer same sector+industry only. Fall back to same sector only when exact matches are scarce.
        # Product requirement: only backfill with sector peers when fewer than 10 exact peers exist.
        fallback_threshold = 10
        use_sector_fallback = len(exact_matches) < fallback_threshold

        if use_sector_fallback:
            all_matches = exact_matches + sector_only_matches
            match_type = "sector_only" if all_matches else "no_matches"
        else:
            all_matches = exact_matches
            match_type = "sector_and_industry" if all_matches else "no_matches"

        # Always prioritize same-industry peers at the top when mixed with fallback peers.
        if target_industry:
            all_matches.sort(
                key=lambda x: (
                    0 if x.get("industry") == target_industry else 1,
                    -(x["market_cap"] if isinstance(x.get("market_cap"), (int, float)) else 0),
                    x.get("ticker", ""),
                )
            )

        total_count = len(all_matches)
        similar_stocks = all_matches[safe_offset:safe_offset + safe_limit]

        # Fill current_price/change_percent in one batch call.
        self._enrich_similar_tickers_with_batch_quotes(similar_stocks)
        
        return {
            "ticker": ticker,
            "sector": target_sector,
            "industry": target_industry,
            "similar_tickers": similar_stocks,
            "count": len(similar_stocks),
            "total_count": total_count,
            "limit": safe_limit,
            "offset": safe_offset,
            "has_more": safe_offset + len(similar_stocks) < total_count,
            "match_type": match_type,
            "method": "yahooquery_batch"
        }

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        """Convert values to float when possible; return None for invalid values."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, dict):
            # YahooQuery sometimes returns wrapped numeric objects like {"raw": 293.31, "fmt": "293.31"}.
            for key in ("raw", "value", "fmt", "longFmt"):
                if key in value:
                    return InfoFetcher._coerce_float(value.get(key))
            return None
        if isinstance(value, numbers.Real):
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        try:
            val = float(value)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        except Exception:
            return None

    @staticmethod
    def _get_symbol_payload(batch_map: Any, symbol: str) -> Dict[str, Any]:
        """Extract per-symbol payload from yahooquery batch response."""
        if not isinstance(batch_map, dict):
            return {}
        symbol_upper = str(symbol).upper()
        payload = batch_map.get(symbol)
        if payload is None:
            for key, value in batch_map.items():
                if str(key).upper() == symbol_upper:
                    payload = value
                    break
        if isinstance(payload, dict) and not payload.get("error"):
            return payload
        # Single-symbol yahooquery responses can already be the payload dict (not nested by symbol key).
        # Detect common market-data keys and use the dict directly.
        direct_keys = {
            "regularMarketPrice",
            "targetMeanPrice",
            "targetLowPrice",
            "targetHighPrice",
            "currentPrice",
            "recommendationKey",
        }
        if direct_keys.intersection(batch_map.keys()) and not batch_map.get("error"):
            return batch_map
        return {}

    def _enrich_similar_tickers_with_batch_quotes(self, similar_tickers: List[Dict[str, Any]]) -> None:
        """Populate price and fundamentals using one yahooquery get_modules() call to reduce UI delay."""
        if not similar_tickers:
            return

        symbols = [ticker.get("ticker") for ticker in similar_tickers if ticker.get("ticker")]
        if not symbols:
            return

        try:
            from yahooquery import Ticker as YahooQueryTicker
        except Exception:
            return

        try:
            ticker_obj = YahooQueryTicker(symbols)
        except Exception:
            return

        try:
            raw = ticker_obj.get_modules("price summaryDetail financialData defaultKeyStatistics")
        except Exception:
            raw = {}

        if not isinstance(raw, dict):
            return

        for ticker in similar_tickers:
            symbol = ticker.get("ticker")
            if not symbol:
                continue

            per_symbol = raw.get(symbol) or raw.get((symbol or "").upper()) or raw.get((symbol or "").lower())
            if not isinstance(per_symbol, dict):
                continue
            symbol_price = per_symbol.get("price") if isinstance(per_symbol.get("price"), dict) else {}
            symbol_summary_detail = per_symbol.get("summaryDetail") if isinstance(per_symbol.get("summaryDetail"), dict) else {}
            symbol_financial_data = per_symbol.get("financialData") if isinstance(per_symbol.get("financialData"), dict) else {}
            symbol_key_stats = per_symbol.get("defaultKeyStatistics") if isinstance(per_symbol.get("defaultKeyStatistics"), dict) else {}

            market_price = self._coerce_float(symbol_price.get("regularMarketPrice"))
            if market_price is not None:
                ticker["current_price"] = round(market_price, 2)

            change_percent = self._coerce_float(symbol_price.get("regularMarketChangePercent"))
            if change_percent is not None:
                # yahooquery `regularMarketChangePercent` is fractional (e.g. -0.016 = -1.6%).
                ticker["change_percent"] = round(change_percent * 100.0, 2)

            market_cap = self._coerce_float(symbol_price.get("marketCap"))
            if market_cap is None:
                market_cap = self._coerce_float(symbol_summary_detail.get("marketCap"))
            if market_cap is not None:
                ticker["market_cap"] = int(market_cap)

            trailing_pe = self._coerce_float(symbol_summary_detail.get("trailingPE"))
            if trailing_pe is not None:
                ticker["trailing_pe"] = trailing_pe

            forward_pe = self._coerce_float(symbol_summary_detail.get("forwardPE"))
            if forward_pe is not None:
                ticker["forward_pe"] = forward_pe

            dividend_yield = self._coerce_float(symbol_summary_detail.get("dividendYield"))
            if dividend_yield is not None:
                ticker["dividend_yield"] = dividend_yield

            beta = self._coerce_float(symbol_summary_detail.get("beta"))
            if beta is None:
                beta = self._coerce_float(symbol_key_stats.get("beta"))
            if beta is not None:
                ticker["beta"] = beta

            fifty_two_week_high = self._coerce_float(symbol_summary_detail.get("fiftyTwoWeekHigh"))
            if fifty_two_week_high is None:
                fifty_two_week_high = self._coerce_float(symbol_price.get("fiftyTwoWeekHigh"))
            if fifty_two_week_high is not None:
                ticker["fifty_two_week_high"] = fifty_two_week_high

            fifty_two_week_low = self._coerce_float(symbol_summary_detail.get("fiftyTwoWeekLow"))
            if fifty_two_week_low is None:
                fifty_two_week_low = self._coerce_float(symbol_price.get("fiftyTwoWeekLow"))
            if fifty_two_week_low is not None:
                ticker["fifty_two_week_low"] = fifty_two_week_low

            trailing_eps = self._coerce_float(symbol_key_stats.get("trailingEps"))
            if trailing_eps is not None:
                ticker["trailing_eps"] = trailing_eps

            forward_eps = self._coerce_float(symbol_key_stats.get("forwardEps"))
            if forward_eps is not None:
                ticker["forward_eps"] = forward_eps

            ebitda = self._coerce_float(symbol_financial_data.get("ebitda"))
            if ebitda is not None:
                ticker["ebitda"] = int(ebitda)

            revenue = self._coerce_float(symbol_financial_data.get("totalRevenue"))
            if revenue is not None:
                ticker["revenue"] = int(revenue)

            profit_margin = self._coerce_float(symbol_financial_data.get("profitMargins"))
            if profit_margin is not None:
                ticker["profit_margin"] = profit_margin

            gross_margin = self._coerce_float(symbol_financial_data.get("grossMargins"))
            if gross_margin is not None:
                ticker["gross_margin"] = gross_margin

            operating_margin = self._coerce_float(symbol_financial_data.get("operatingMargins"))
            if operating_margin is not None:
                ticker["operating_margin"] = operating_margin

            ebitda_margin = self._coerce_float(symbol_financial_data.get("ebitdaMargins"))
            if ebitda_margin is not None:
                ticker["ebitda_margin"] = ebitda_margin

            target_mean_price = self._coerce_float(symbol_financial_data.get("targetMeanPrice"))
            if target_mean_price is not None:
                ticker["target_mean_price"] = target_mean_price

            recommendation_key = symbol_financial_data.get("recommendationKey")
            if isinstance(recommendation_key, str) and recommendation_key.strip():
                ticker["recommendation_key"] = recommendation_key.strip()

    def get_daily_market_movers(self, count: int = 25) -> Dict[str, Any]:
        """Get daily top gainers, losers, and most active from yahooquery Screener (US market)."""
        from yahooquery import Screener

        def _normalize_quote(q: Dict[str, Any]) -> Dict[str, Any]:
            price = self._coerce_float(q.get("regularMarketPrice"))
            change = self._coerce_float(q.get("regularMarketChange"))
            change_pct = self._coerce_float(q.get("regularMarketChangePercent"))
            # yahooquery screener may return change percent as percentage (61.21) or fractional; normalize to percentage
            if change_pct is not None and abs(change_pct) <= 1.5 and change_pct != 0:
                change_pct = change_pct * 100.0
            return {
                "symbol": (q.get("symbol") or "").strip() or None,
                "shortName": (q.get("shortName") or q.get("longName") or "").strip() or None,
                "regularMarketPrice": round(price, 2) if price is not None else None,
                "regularMarketChange": round(change, 2) if change is not None else None,
                "regularMarketChangePercent": round(change_pct, 2) if change_pct is not None else None,
                "regularMarketPreviousClose": self._coerce_float(q.get("regularMarketPreviousClose")),
                "regularMarketVolume": int(q["regularMarketVolume"]) if q.get("regularMarketVolume") is not None else None,
            }

        count = max(1, min(100, count))
        screen_ids = ["day_gainers", "day_losers", "most_actives"]
        raw = Screener().get_screeners(screen_ids, count=count)
        if not isinstance(raw, dict):
            return {"gainers": [], "losers": [], "most_active": []}

        gainers_data = raw.get("day_gainers")
        losers_data = raw.get("day_losers")
        most_actives_data = raw.get("most_actives")
        quotes_g = gainers_data.get("quotes", []) if isinstance(gainers_data, dict) else []
        quotes_l = losers_data.get("quotes", []) if isinstance(losers_data, dict) else []
        quotes_ma = most_actives_data.get("quotes", []) if isinstance(most_actives_data, dict) else []

        gainers = [_normalize_quote(q) for q in quotes_g if isinstance(q, dict) and q.get("symbol")]
        losers = [_normalize_quote(q) for q in quotes_l if isinstance(q, dict) and q.get("symbol")]
        most_active = [_normalize_quote(q) for q in quotes_ma if isinstance(q, dict) and q.get("symbol")]

        # Enrich with sector/industry via one batch call (screener quotes don't include sector)
        all_symbols = [r["symbol"] for r in gainers + losers + most_active if r.get("symbol")]
        sector_map = self._fetch_sector_info_batch_yahooquery(all_symbols) if all_symbols else {}
        for row in gainers + losers + most_active:
            sym = row.get("symbol")
            if sym and sym in sector_map:
                info = sector_map[sym]
                row["sector"] = info.get("sector")
                row["industry"] = info.get("industry")

        return {"gainers": gainers, "losers": losers, "most_active": most_active}

    # Curated tickers for market overview: (group_key, ticker, display_name). At least 12 per section.
    MARKET_OVERVIEW_TICKERS = [
        # US indices (Yahoo symbols)
        ("indices", "^GSPC", "S&P 500"),
        ("indices", "^IXIC", "Nasdaq"),
        ("indices", "^DJI", "Dow Jones"),
        ("indices", "^NDX", "Nasdaq 100"),
        ("indices", "^RUT", "Russell 2000"),
        ("indices", "SPY", "S&P 500 ETF"),
        ("indices", "QQQ", "Nasdaq 100 ETF"),
        ("indices", "DIA", "Dow Jones ETF"),
        ("indices", "IWM", "Russell 2000 ETF"),
        ("indices", "MDY", "S&P MidCap 400"),
        ("indices", "VOO", "S&P 500 (Vanguard)"),
        ("indices", "VTI", "US Total Market"),
        # Sectors (SPDRs / sector ETFs)
        ("sectors", "XLK", "Technology"),
        ("sectors", "XLF", "Financials"),
        ("sectors", "XLE", "Energy"),
        ("sectors", "XLV", "Healthcare"),
        ("sectors", "XLI", "Industrials"),
        ("sectors", "XLY", "Consumer Discretionary"),
        ("sectors", "XLP", "Consumer Staples"),
        ("sectors", "XLB", "Materials"),
        ("sectors", "XLU", "Utilities"),
        ("sectors", "XLC", "Communication"),
        ("sectors", "VGT", "Technology (Vanguard)"),
        ("sectors", "KRE", "Regional Banks"),
        # International / regions (indices from exchanges + ETFs) – 24+ regions
        ("international", "EFA", "Developed ex-US"),
        ("international", "EEM", "Emerging Markets"),
        ("international", "VEA", "Developed Markets"),
        ("international", "VWO", "Emerging Markets (Vanguard)"),
        # Israel (Tel Aviv)
        ("international", "^TA125.TA", "Israel TA-125"),
        # Arab / Gulf
        ("international", "^TASI.SR", "Saudi Arabia TASI"),
        ("international", "KSA", "Saudi Arabia (iShares)"),
        ("international", "UAE", "UAE (iShares)"),
        ("international", "QAT", "Qatar (iShares)"),
        ("international", "BAX", "Baxter International Inc."),
        ("international", "KWT", "Kuwait (iShares)"),
        # Europe indices
        ("international", "^FTSE", "UK FTSE 100"),
        ("international", "^GDAXI", "Germany DAX"),
        ("international", "^FCHI", "France CAC 40"),
        ("international", "^STOXX50E", "Euro Stoxx 50"),
        ("international", "EWG", "Germany (iShares)"),
        ("international", "EWU", "UK (iShares)"),
        ("international", "^IBEX", "Spain IBEX 35"),
        ("international", "^AEX", "Netherlands AEX"),
        ("international", "^SSMI", "Switzerland SMI"),
        ("international", "^OMXSPI", "Sweden OMX"),
        ("international", "^ATX", "Austria ATX"),
        ("international", "^BFX", "Belgium BEL 20"),
        ("international", "^OMXC20", "Denmark OMX Copenhagen"),
        ("international", "^OMXH25", "Finland OMX Helsinki"),
        ("international", "GD.AT", "Greece Athens General"),
        ("international", "EIRL", "Ireland (iShares)"),
        ("international", "^OSEAX", "Norway Oslo OBX"),
        # Asia-Pacific indices
        ("international", "^N225", "Japan Nikkei 225"),
        ("international", "^HSI", "Hong Kong Hang Seng"),
        ("international", "^STI", "Singapore Straits"),
        ("international", "^AXJO", "Australia ASX 200"),
        ("international", "^KS11", "South Korea KOSPI"),
        ("international", "^TWII", "Taiwan TAIEX"),
        ("international", "^BSESN", "India Sensex"),
        ("international", "^NSEI", "India Nifty 50"),
        ("international", "^JKSE", "Indonesia IDX"),
        ("international", "^KLSE", "Malaysia KLCI"),
        ("international", "000001.SS", "China Shanghai"),
        ("international", "^SET.BK", "Thailand SET"),
        ("international", "PSEI.PS", "Philippines PSEi"),
        ("international", "VNM", "Vietnam (VanEck)"),
        ("international", "XBAK.DE", "Pakistan KSE 100"),
        ("international", "^NZ50", "New Zealand NZX 50"),
        ("international", "ENZL", "New Zealand (iShares)"),
        ("international", "EWJ", "Japan (iShares)"),
        ("international", "FXI", "China (iShares)"),
        ("international", "INDA", "India (iShares)"),
        ("international", "EWM", "Malaysia (iShares)"),
        ("international", "EIDO", "Indonesia (iShares)"),
        # Turkey
        ("international", "XU100.IS", "Turkey BIST 100"),
        ("international", "TUR", "Turkey (iShares)"),
        # Americas
        ("international", "^GSPTSE", "Canada TSX"),
        ("international", "^BVSP", "Brazil Bovespa"),
        ("international", "^MXX", "Mexico IPC"),
        ("international", "^IPSA", "Chile IPSA"),
        ("international", "^MERV", "Argentina Merval"),
        ("international", "ICOLCAP.CL", "Colombia COLCAP"),
        ("international", "EPU", "Peru (iShares)"),
        ("international", "EWC", "Canada (iShares)"),
        ("international", "EWZ", "Brazil (iShares)"),
        ("international", "EWA", "Australia (iShares)"),
        # Africa
        ("international", "AFK", "Pan-Africa ETF"),
        ("international", "^JN0U.JO", "South Africa Top 40"),
        ("international", "EZA", "South Africa (iShares)"),
        # Commodities / materials (ETFs and common proxies) / materials (ETFs and common proxies)
        ("commodities", "GLD", "Gold"),
        ("commodities", "SLV", "Silver"),
        ("commodities", "IAU", "Gold (iShares)"),
        ("commodities", "CL=F", "Oil (WTI)"),
        ("commodities", "UNG", "Natural Gas"),
        ("commodities", "DBA", "Agriculture"),
        ("commodities", "DBC", "Broad Commodities"),
        ("commodities", "CPER", "Copper"),
        ("commodities", "PALL", "Palladium"),
        ("commodities", "PLTM", "Platinum"),
        ("commodities", "WEAT", "Wheat"),
        ("commodities", "CORN", "Corn"),
    ]

    # Overview pane only needs a small regions set (6*3 tiles). Map tab fetches full list separately.
    OVERVIEW_INTERNATIONAL_TICKERS = [
        (g, t, n)
        for g, t, n in MARKET_OVERVIEW_TICKERS
        if g == "international"
    ][:18]

    def get_market_overview(
        self,
        limit_indices: int = 50,
        offset_indices: int = 0,
        limit_sectors: int = 50,
        offset_sectors: int = 0,
        limit_regions: int = 50,
        offset_regions: int = 0,
        limit_commodities: int = 50,
        offset_commodities: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        """Get high-level market overview: indices, sectors, international, commodities with prices and change.
        range_: 1d (daily), 1w (1 week), 1mo (1 month), 3mo, 6mo, ytd.
        Within each section, items are ordered by absolute change (biggest movers first). Pagination via limit/offset."""
        valid_ranges = ("1d", "1w", "1mo", "3mo", "6mo", "ytd")
        range_ = range_ if range_ in valid_ranges else "1d"
        svc = self._get_market_data_service()
        # Overview pane requests small region slice (e.g. 6); use 18 region tickers. Map requests 100 and get full list.
        use_overview_regions = limit_regions <= 18
        by_group: Dict[str, List[tuple]] = {"indices": [], "sectors": [], "international": [], "commodities": []}
        for group_key, ticker, name in self.MARKET_OVERVIEW_TICKERS:
            if group_key == "international" and use_overview_regions:
                continue
            by_group[group_key].append((ticker.upper(), name))
        if use_overview_regions:
            for _, ticker, name in self.OVERVIEW_INTERNATIONAL_TICKERS:
                by_group["international"].append((ticker.upper(), name))
        if use_overview_regions:
            other = {row[1].upper() for row in self.MARKET_OVERVIEW_TICKERS if row[0] != "international"}
            region = {t.upper() for _, t, _ in self.OVERVIEW_INTERNATIONAL_TICKERS}
            tickers = list(other | region)
        else:
            tickers = list({row[1].upper() for row in self.MARKET_OVERVIEW_TICKERS})
        # Fetch each group separately so we use smaller, homogeneous batches (same as regional test).
        # One big combined list causes more Yahoo timeouts/failures and yields missing data for some tickers.
        quotes: Dict[str, Any] = {}
        for group_key in ("indices", "sectors", "international", "commodities"):
            group_tickers = [t for t, _ in by_group[group_key]]
            if not group_tickers:
                continue
            group_quotes = svc.get_multiple_quotes_batch_with_range(group_tickers, range_)
            for t, q in group_quotes.items():
                if q is not None:
                    quotes[t] = q
        # Fallback: if we didn't do per-group (e.g. empty groups), use original combined fetch
        if not quotes and tickers:
            quotes = svc.get_multiple_quotes_batch_with_range(tickers, range_)

        def _build_and_sort(group_key: str) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            for t, name in by_group[group_key]:
                q = quotes.get(t)
                if q is None:
                    item = {
                        "ticker": t,
                        "name": name,
                        "price": None,
                        "change": None,
                        "changePercent": None,
                    }
                else:
                    item = {
                        "ticker": t,
                        "name": name,
                        "price": round(float(q.current_price), 2),
                        "change": round(float(q.daily_change), 2),
                        "changePercent": round(float(q.daily_change_percent), 2),
                    }
                items.append(item)
            # Sort by absolute change (desc): biggest movers first; None treated as 0 (end)
            items.sort(key=lambda x: abs(x.get("changePercent") or 0), reverse=True)
            return items

        sorted_indices = _build_and_sort("indices")
        sorted_sectors = _build_and_sort("sectors")
        sorted_international = _build_and_sort("international")
        sorted_commodities = _build_and_sort("commodities")

        return {
            "indices": sorted_indices[offset_indices : offset_indices + limit_indices],
            "sectors": sorted_sectors[offset_sectors : offset_sectors + limit_sectors],
            "international": sorted_international[offset_regions : offset_regions + limit_regions],
            "commodities": sorted_commodities[offset_commodities : offset_commodities + limit_commodities],
            "totalIndices": len(sorted_indices),
            "totalSectors": len(sorted_sectors),
            "totalRegions": len(sorted_international),
            "totalCommodities": len(sorted_commodities),
        }

    def get_market_overview_section(
        self,
        section: str,
        limit: int = 50,
        offset: int = 0,
        range_: str = "1d",
    ) -> Dict[str, Any]:
        """
        Get a single section of the market overview (indices, sectors, regions, commodities).

        Returns a compact payload with just the requested section:
        {
          "section": "indices" | "sectors" | "regions" | "commodities",
          "items": [...],
          "total": int
        }
        """
        valid_ranges = ("1d", "1w", "1mo", "3mo", "6mo", "ytd")
        range_ = range_ if range_ in valid_ranges else "1d"

        normalized_section = section.lower()
        section_map = {
            "indices": "indices",
            "sectors": "sectors",
            "regions": "international",
            "international": "international",
            "commodities": "commodities",
        }
        if normalized_section not in section_map:
            raise ValueError(
                f"Invalid section '{section}'. Expected one of: indices, sectors, regions, commodities."
            )

        group_key = section_map[normalized_section]
        svc = self._get_market_data_service()

        # Collect tickers only for the requested group.
        group_tickers: List[tuple] = []
        for g_key, ticker, name in self.MARKET_OVERVIEW_TICKERS:
            if g_key == group_key:
                group_tickers.append((ticker.upper(), name))

        if not group_tickers:
            return {"section": normalized_section, "items": [], "total": 0}

        unique_tickers = list({t for (t, _name) in group_tickers})
        quotes = svc.get_multiple_quotes_batch_with_range(unique_tickers, range_)

        items: List[Dict[str, Any]] = []
        for t, name in group_tickers:
            q = quotes.get(t)
            if q is None:
                item = {
                    "ticker": t,
                    "name": name,
                    "price": None,
                    "change": None,
                    "changePercent": None,
                }
            else:
                item = {
                    "ticker": t,
                    "name": name,
                    "price": round(float(q.current_price), 2),
                    "change": round(float(q.daily_change), 2),
                    "changePercent": round(float(q.daily_change_percent), 2),
                }
            items.append(item)

        # Sort by absolute change (desc): biggest movers first; None treated as 0 (end)
        items.sort(key=lambda x: abs(x.get("changePercent") or 0), reverse=True)
        total = len(items)
        paged = items[offset : offset + limit]

        # Normalize section name in response to external contract (regions instead of international).
        response_section = (
            "regions" if group_key == "international" else group_key
        )
        return {
            "section": response_section,
            "items": paged,
            "total": total,
        }

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        """Get company officers/management team from Yahoo Finance."""
        import yfinance as yf
        
        ticker = ticker.upper()
        
        try:
            t = yf.Ticker(ticker)
            # Get company officers from the info dict
            info = t.info
            officers_data = info.get("companyOfficers", [])
            
            if not officers_data:
                return {
                    "ticker": ticker,
                    "officers": [],
                    "count": 0,
                }
            
            # Process officers data
            officers = []
            for officer in officers_data:
                if not isinstance(officer, dict):
                    continue
                
                # Extract relevant fields
                name = officer.get("name")
                title = officer.get("title")
                age = officer.get("age")
                year_born = officer.get("yearBorn")
                fiscal_year = officer.get("fiscalYear")
                total_pay = officer.get("totalPay")
                exercised_value = officer.get("exercisedValue")
                unexercised_value = officer.get("unexercisedValue")
                
                # Skip if no name or title
                if not name or not title:
                    continue
                
                officer_info = {
                    "name": name,
                    "title": title,
                    "age": age,
                    "year_born": year_born,
                    "fiscal_year": fiscal_year,
                    "total_pay": total_pay,
                    "exercised_value": exercised_value,
                    "unexercised_value": unexercised_value,
                }
                
                officers.append(officer_info)
            
            return {
                "ticker": ticker,
                "officers": officers,
                "count": len(officers),
            }
            
        except Exception as e:
            return {
                "ticker": ticker,
                "officers": [],
                "count": 0,
                "error": str(e),
            }




# Singleton used by the API router (injected with services from main.py when needed)
_engine: Optional[InfoFetcher] = None


def get_info_fetcher(
    market_data_service: Optional[Any] = None,
    news_service: Optional[Any] = None,
):
    """Get the shared InfoFetcher instance, wrapped with CachedInfoFetcher for cache layer."""
    global _engine
    if _engine is None:
        raw = InfoFetcher(market_data_service=market_data_service, news_service=news_service)
        from services.cached_info_fetcher import CachedInfoFetcher
        _engine = CachedInfoFetcher(raw)
    return _engine

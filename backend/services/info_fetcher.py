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
        self._load_major_stocks_sectors()

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
    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """Get company profile (name, sector, industry, etc.)."""
        import yfinance as yf
        ticker = ticker.upper()
        try:
            info = yf.Ticker(ticker).info
            quote_type = info.get("quoteType")
            # Yahoo often omits quoteType for indices; infer INDEX when symbol starts with ^
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
            # Infer index for ^ tickers even on error
            quote_type = "INDEX" if ticker.startswith("^") else None
            return {
                "name": ticker,
                "sector": "N/A",
                "industry": "N/A",
                "exchange": "N/A",
                "country": "N/A",
                "website": "N/A",
                "quoteType": quote_type,
            }

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

    def get_stock_data(self, ticker: str, start_date: str, end_date: str) -> str:
        """Get OHLCV time series as string (for agents). Uses tradingagents route_to_vendor."""
        route = self._get_route_to_vendor()
        return route("get_stock_data", ticker.upper(), start_date, end_date)

    def get_financial_charts(self, ticker: str, freq: str = "annual") -> Dict[str, Any]:
        """Get chart-ready time series for fundamentals (Revenue, EPS, Debt, FCF, etc.)."""
        from services.financial_charts_service import get_financial_charts as get_charts
        return get_charts(ticker.upper(), freq=freq)

    def get_analyst_recommendations(self, ticker: str) -> Dict[str, Any]:
        """Get analyst recommendations from yfinance."""
        try:
            _tradingagents_route_to_vendor()  # ensure path
            from ai_engine.tradingagents.dataflows.y_finance import get_analyst_recommendations as get_rec
            return get_rec(ticker.upper())
        except Exception as e:
            return {
                "ticker": ticker.upper(),
                "recommendation": None,
                "target_price": None,
                "breakdown": {},
                "total_analysts": 0,
                "latest_date": None,
                "error": str(e),
            }

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
    def _load_major_stocks_sectors(self):
        """Load major stocks sector/industry data from JSON file.
        
        Loads pre-generated sector/industry data from backend/data/major_stocks_sectors.json
        into the cache. This avoids API rate limits and provides instant lookups.
        
        If the file doesn't exist, the cache remains empty and data will be fetched
        on-demand when needed.
        """
        data_file = Path(__file__).parent.parent / "data" / "major_stocks_sectors.json"
        
        if not data_file.exists():
            # File doesn't exist yet - will fetch on-demand
            return
        
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Load into cache
            with self._sector_cache_lock:
                for ticker, info in data.items():
                    # Only cache if we have valid data (no error field)
                    if not info.get("error"):
                        self._sector_cache[ticker] = info
            
            # Store list of major tickers for similar ticker lookups
            self._major_tickers = list(data.keys())
            
        except Exception as e:
            # If loading fails, log but don't crash - will fetch on-demand
            print(f"Warning: Could not load major_stocks_sectors.json: {e}")
            self._major_tickers = []
    
    def _get_or_fetch_sector_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get sector/industry info from cache or fetch from Yahoo Finance.
        
        This builds up an in-memory cache on-demand to speed up subsequent requests.
        """
        import yfinance as yf
        
        ticker = ticker.upper()
        
        # Check cache first
        with self._sector_cache_lock:
            if ticker in self._sector_cache:
                return self._sector_cache[ticker]
        
        # Fetch from Yahoo Finance
        try:
            info = yf.Ticker(ticker).info
            sector_info = {
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "quote_type": info.get("quoteType"),
                "trailing_pe": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "trailing_eps": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),
                "ebitda": info.get("ebitda"),
                "revenue": info.get("totalRevenue"),
                "profit_margin": info.get("profitMargins"),
                "gross_margin": info.get("grossMargins"),
                "operating_margin": info.get("operatingMargins"),
                "ebitda_margin": info.get("ebitdaMargins"),
                "beta": info.get("beta"),
                "dividend_yield": info.get("dividendYield"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                "target_mean_price": info.get("targetMeanPrice"),
                "recommendation_key": info.get("recommendationKey"),
            }
            
            # Cache it
            with self._sector_cache_lock:
                self._sector_cache[ticker] = sector_info
            
            return sector_info
        except Exception:
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
        
        Uses the cached sector/industry data from self._sector_cache which is populated
        by the background prefetch process on first use.
        """
        # Use instance variable for major tickers list
        major_tickers = [t for t in self._major_tickers if t != ticker]
        
        exact_matches: List[Dict[str, Any]] = []
        sector_only_matches: List[Dict[str, Any]] = []
        
        for candidate_ticker in major_tickers:
            # Get from cache (should be prefetched by now, but will fetch if not)
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
        payload = batch_map.get(symbol)
        if isinstance(payload, dict) and not payload.get("error"):
            return payload
        return {}

    def _enrich_similar_tickers_with_batch_quotes(self, similar_stocks: List[Dict[str, Any]]) -> None:
        """Populate price and fundamentals fields using batched yahooquery requests."""
        if not similar_stocks:
            return

        symbols = [stock.get("ticker") for stock in similar_stocks if stock.get("ticker")]
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

        batch_price: Dict[str, Any] = {}
        batch_summary_detail: Dict[str, Any] = {}
        batch_financial_data: Dict[str, Any] = {}
        batch_key_stats: Dict[str, Any] = {}

        try:
            resp = ticker_obj.price
            if isinstance(resp, dict):
                batch_price = resp
        except Exception:
            pass

        try:
            resp = ticker_obj.summary_detail
            if isinstance(resp, dict):
                batch_summary_detail = resp
        except Exception:
            pass

        try:
            resp = ticker_obj.financial_data
            if isinstance(resp, dict):
                batch_financial_data = resp
        except Exception:
            pass

        try:
            resp = ticker_obj.key_stats
            if isinstance(resp, dict):
                batch_key_stats = resp
        except Exception:
            pass

        for stock in similar_stocks:
            symbol = stock.get("ticker")
            if not symbol:
                continue

            symbol_price = self._get_symbol_payload(batch_price, symbol)
            symbol_summary_detail = self._get_symbol_payload(batch_summary_detail, symbol)
            symbol_financial_data = self._get_symbol_payload(batch_financial_data, symbol)
            symbol_key_stats = self._get_symbol_payload(batch_key_stats, symbol)

            market_price = self._coerce_float(symbol_price.get("regularMarketPrice"))
            if market_price is not None:
                stock["current_price"] = round(market_price, 2)

            change_percent = self._coerce_float(symbol_price.get("regularMarketChangePercent"))
            if change_percent is not None:
                # yahooquery `regularMarketChangePercent` is fractional (e.g. -0.016 = -1.6%).
                stock["change_percent"] = round(change_percent * 100.0, 2)

            market_cap = self._coerce_float(symbol_price.get("marketCap"))
            if market_cap is None:
                market_cap = self._coerce_float(symbol_summary_detail.get("marketCap"))
            if market_cap is not None:
                stock["market_cap"] = int(market_cap)

            trailing_pe = self._coerce_float(symbol_summary_detail.get("trailingPE"))
            if trailing_pe is not None:
                stock["trailing_pe"] = trailing_pe

            forward_pe = self._coerce_float(symbol_summary_detail.get("forwardPE"))
            if forward_pe is not None:
                stock["forward_pe"] = forward_pe

            dividend_yield = self._coerce_float(symbol_summary_detail.get("dividendYield"))
            if dividend_yield is not None:
                stock["dividend_yield"] = dividend_yield

            beta = self._coerce_float(symbol_summary_detail.get("beta"))
            if beta is None:
                beta = self._coerce_float(symbol_key_stats.get("beta"))
            if beta is not None:
                stock["beta"] = beta

            fifty_two_week_high = self._coerce_float(symbol_summary_detail.get("fiftyTwoWeekHigh"))
            if fifty_two_week_high is None:
                fifty_two_week_high = self._coerce_float(symbol_price.get("fiftyTwoWeekHigh"))
            if fifty_two_week_high is not None:
                stock["fifty_two_week_high"] = fifty_two_week_high

            fifty_two_week_low = self._coerce_float(symbol_summary_detail.get("fiftyTwoWeekLow"))
            if fifty_two_week_low is None:
                fifty_two_week_low = self._coerce_float(symbol_price.get("fiftyTwoWeekLow"))
            if fifty_two_week_low is not None:
                stock["fifty_two_week_low"] = fifty_two_week_low

            trailing_eps = self._coerce_float(symbol_key_stats.get("trailingEps"))
            if trailing_eps is not None:
                stock["trailing_eps"] = trailing_eps

            forward_eps = self._coerce_float(symbol_key_stats.get("forwardEps"))
            if forward_eps is not None:
                stock["forward_eps"] = forward_eps

            ebitda = self._coerce_float(symbol_financial_data.get("ebitda"))
            if ebitda is not None:
                stock["ebitda"] = int(ebitda)

            revenue = self._coerce_float(symbol_financial_data.get("totalRevenue"))
            if revenue is not None:
                stock["revenue"] = int(revenue)

            profit_margin = self._coerce_float(symbol_financial_data.get("profitMargins"))
            if profit_margin is not None:
                stock["profit_margin"] = profit_margin

            gross_margin = self._coerce_float(symbol_financial_data.get("grossMargins"))
            if gross_margin is not None:
                stock["gross_margin"] = gross_margin

            operating_margin = self._coerce_float(symbol_financial_data.get("operatingMargins"))
            if operating_margin is not None:
                stock["operating_margin"] = operating_margin

            ebitda_margin = self._coerce_float(symbol_financial_data.get("ebitdaMargins"))
            if ebitda_margin is not None:
                stock["ebitda_margin"] = ebitda_margin

            target_mean_price = self._coerce_float(symbol_financial_data.get("targetMeanPrice"))
            if target_mean_price is not None:
                stock["target_mean_price"] = target_mean_price

            recommendation_key = symbol_financial_data.get("recommendationKey")
            if isinstance(recommendation_key, str) and recommendation_key.strip():
                stock["recommendation_key"] = recommendation_key.strip()

    def get_company_officers(self, ticker: str) -> Dict[str, Any]:
        """Get company officers/management team from Yahoo Finance."""
        import yfinance as yf
        import pandas as pd
        
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

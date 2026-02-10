"""
Information Fetcher Engine: single entry point for all market/data fetching.

- News: app news API only (services/news_fetcher → Yahoo). Same data for UI and agents.
- Other data: yfinance in-engine or tradingagents where needed.
Used by both the dashboard HTTP API and (via info service client) by AI agents.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Lazy tradingagents import to avoid hard dependency at import time
def _tradingagents_route_to_vendor():
    import sys
    backend_dir = Path(__file__).resolve().parent.parent
    tradingagents_dir = backend_dir.parent  # repo root (backend is at root)
    if str(tradingagents_dir) not in sys.path:
        sys.path.insert(0, str(tradingagents_dir))
    from tradingagents.dataflows.interface import route_to_vendor
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
        """Get historical OHLCV data. Uses yfinance in-engine; can be overridden."""
        import yfinance as yf
        ticker = ticker.upper()
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period, interval=interval)
        if hist.empty:
            return {"ticker": ticker, "period": period, "interval": interval, "data": [], "count": 0}
        data = []
        for date, row in hist.iterrows():
            d = date
            if hasattr(d, "tz_localize") and d.tzinfo is not None:
                d = d.tz_localize(None)
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
            from tradingagents.dataflows.y_finance import get_fundamentals_core
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
            from tradingagents.dataflows.y_finance import get_analyst_recommendations as get_rec
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

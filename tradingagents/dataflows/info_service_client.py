"""
Client for the Information Fetcher Service API.

When INFO_SERVICE_URL (or config info_service_url) is set, agent tools can use
this client to fetch data from the same service as the dashboard UI, ensuring
consistent data and a single source of truth.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None


def _get_info_service_base_url() -> Optional[str]:
    """Base URL for the info service (e.g. http://localhost:8002)."""
    url = os.getenv("INFO_SERVICE_URL", "").strip()
    if url:
        return url.rstrip("/")
    try:
        from tradingagents.dataflows.config import get_config
        cfg = get_config()
        url = (cfg.get("info_service_url") or "").strip()
        return url.rstrip("/") if url else None
    except Exception:
        return None


def _get(session: Optional[requests.Session], base_url: str, path: str, params: Optional[Dict] = None, timeout: int = 30) -> Any:
    if requests is None:
        raise RuntimeError("requests is required for info service client; install with: pip install requests")
    url = urljoin(base_url + "/", path.lstrip("/"))
    r = (session or requests).get(url, params=params, timeout=timeout)
    r.raise_for_status()
    ct = r.headers.get("Content-Type", "")
    if "application/json" in ct:
        return r.json()
    return r.text


def get_quote(ticker: str, base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch quote from info service. Returns dict or None if not found."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(None, base_url, f"/api/data/quote/{ticker.upper()}")
    except Exception:
        return None


def get_news(ticker: str, start_date: str, end_date: str, base_url: Optional[str] = None, lookback_days: int = 7) -> str:
    """Fetch news from info service. Returns JSON string with articles (same shape as route_to_vendor get_news)."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"ticker": ticker.upper(), "lookback_days": lookback_days}
    data = _get(None, base_url, "/api/data/news", params=params)
    if isinstance(data, dict):
        return json.dumps(data)
    return data


def get_stock_data(ticker: str, start_date: str, end_date: str, base_url: Optional[str] = None) -> str:
    """Fetch OHLCV time series from info service. Returns the same string format as route_to_vendor get_stock_data."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"start_date": start_date, "end_date": end_date}
    data = _get(None, base_url, f"/api/data/stock-data/{ticker.upper()}", params=params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return str(data)


def get_fundamentals(ticker: str, base_url: Optional[str] = None) -> str:
    """Fetch fundamentals from info service. Returns JSON string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    data = _get(None, base_url, f"/api/data/fundamentals/{ticker.upper()}")
    if isinstance(data, dict):
        return json.dumps(data)
    return data


def get_company_info(ticker: str, base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch company info from info service."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(None, base_url, f"/api/data/company/{ticker.upper()}")
    except Exception:
        return None


def get_analyst_recommendations(ticker: str, base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch analyst recommendations from info service."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(None, base_url, f"/api/data/analyst-recommendations/{ticker.upper()}")
    except Exception:
        return None


def get_financial_statements(
    ticker: str,
    statement_type: str = "all",
    freq: str = "quarterly",
    base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch financial statements (balance_sheet, cashflow, income_statement) from info service."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(
            None,
            base_url,
            f"/api/data/financial-statements/{ticker.upper()}",
            params={"statement_type": statement_type, "freq": freq},
        )
    except Exception:
        return None


def get_financial_charts(
    ticker: str,
    freq: str = "annual",
    base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch chart-ready financial time series (Revenue, EPS, Debt, FCF, etc.) from info service."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(
            None,
            base_url,
            f"/api/data/financial-charts/{ticker.upper()}",
            params={"freq": freq},
        )
    except Exception:
        return None


def is_configured() -> bool:
    """Return True if info service URL is set."""
    return _get_info_service_base_url() is not None

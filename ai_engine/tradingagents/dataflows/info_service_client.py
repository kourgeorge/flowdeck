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
        from .config import get_config
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


def get_insider_transactions(
    ticker: str,
    base_url: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Fetch insider transactions from info service. Returns JSON string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    data = _get(None, base_url, f"/api/data/insider-transactions/{ticker.upper()}", params={"limit": limit})
    if isinstance(data, dict):
        return json.dumps(data)
    return str(data)


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


def get_edgar_filing_content(
    ticker: str,
    form: Optional[str] = None,
    limit: int = 1,
    base_url: Optional[str] = None,
) -> str:
    """Fetch extracted SEC EDGAR sections (risk factors, MD&A, competition) from info service. Returns formatted string for analyst."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params: Dict[str, Any] = {"limit": limit}
    if form:
        params["form"] = form
    try:
        data = _get(None, base_url, f"/api/data/edgar-filing-content/{ticker.upper()}", params=params)
    except Exception as e:
        return f"Unable to load SEC filing content for {ticker.upper()}: {e}"
    if not isinstance(data, dict):
        return f"No EDGAR filing content available for {ticker.upper()}."
    if data.get("error"):
        return f"No EDGAR filing content available for {ticker.upper()}. {data['error']}"
    filings = data.get("filings") or []
    if not filings:
        return f"No EDGAR filing content available for {ticker.upper()}."
    parts = []
    for f in filings:
        form_type = f.get("form", "")
        filing_date = f.get("filing_date", "")
        sections = f.get("sections") or {}
        parts.append(f"## {form_type} filed {filing_date}")
        parts.append("\n### Risk Factors\n" + (sections.get("risk_factors") or "(none extracted)"))
        parts.append("\n### Management Discussion and Analysis\n" + (sections.get("management_mda") or "(none extracted)"))
        parts.append("\n### Competition\n" + (sections.get("competition") or "(none extracted)"))
        if sections.get("business_overview"):
            parts.append("\n### Business Overview\n" + sections["business_overview"])
        if sections.get("legal_proceedings"):
            parts.append("\n### Legal Proceedings\n" + sections["legal_proceedings"])
        if sections.get("market_risk_disclosures"):
            parts.append("\n### Market Risk Disclosures\n" + sections["market_risk_disclosures"])
    return "\n".join(parts)


def is_configured() -> bool:
    """Return True if info service URL is set."""
    return _get_info_service_base_url() is not None

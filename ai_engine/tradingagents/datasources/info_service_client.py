"""
Client for the Information Fetcher Service API.

When INFO_SERVICE_URL (or config info_service_url) is set, agent tools use this
client to fetch data from the platform backend, ensuring consistent data and
a single source of truth.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None

_url_override: Optional[str] = None


def set_info_service_url(url: Optional[str]) -> None:
    """Set the info service URL (e.g. from TradingAgentsGraph config). Overrides env and default_config."""
    global _url_override
    _url_override = (url or "").strip().rstrip("/") or None


def _get_info_service_base_url() -> Optional[str]:
    """Base URL for the info service (e.g. http://localhost:8002)."""
    url = os.getenv("INFO_SERVICE_URL", "").strip()
    if url:
        return url.rstrip("/")
    if _url_override:
        return _url_override
    try:
        from ..default_config import DEFAULT_CONFIG
        url = (DEFAULT_CONFIG.get("info_service_url") or "").strip()
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    # Fall back to BACKEND_URL (same server; .env.example says INFO_SERVICE_URL defaults to it)
    url = os.getenv("BACKEND_URL", "").strip()
    return url.rstrip("/") if url else None


def _get(session: Optional[requests.Session], base_url: str, path: str, params: Optional[Dict] = None, timeout: int = 60) -> Any:
    """
    Make HTTP GET request to info service.
    
    Args:
        session: Optional requests session for connection pooling
        base_url: Base URL of the info service
        path: API endpoint path
        params: Query parameters
        timeout: Request timeout in seconds (default 60s, increased from 30s to handle data-intensive operations)
    """
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
    """Fetch news from info service. Returns JSON string with articles (same shape as vendor get_news)."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"ticker": ticker.upper(), "lookback_days": lookback_days}
    data = _get(None, base_url, "/api/data/news", params=params, timeout=90)
    if isinstance(data, dict):
        return json.dumps(data)
    return data


def get_reddit_company_social(
    ticker: str,
    start_date: str,
    end_date: str,
    search_terms: List[str],
    base_url: Optional[str] = None,
) -> str:
    """Fetch Reddit company social/discussion feed from info service. search_terms from agent (e.g. company name + ticker from get_quote)."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    if not search_terms or not [t for t in search_terms if t and str(t).strip()]:
        raise ValueError("search_terms is required (e.g. company name and ticker from get_quote/get_news)")
    params = {"start_date": start_date, "end_date": end_date, "search_terms": ",".join(str(t).strip() for t in search_terms if str(t).strip())}
    data = _get(None, base_url, f"/api/data/reddit-company-social/{ticker.upper()}", params=params)
    if isinstance(data, dict) and "data" in data:
        return data["data"] if isinstance(data["data"], str) else json.dumps(data["data"])
    return str(data)


def get_insider_transactions(
    ticker: str,
    base_url: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Fetch insider transactions from info service. Returns JSON string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    data = _get(None, base_url, f"/api/data/insider-transactions/{ticker.upper()}", params={"limit": limit}, timeout=90)
    if isinstance(data, dict):
        return json.dumps(data)
    return str(data)


def get_ticker_data(ticker: str, start_date: str, end_date: str, base_url: Optional[str] = None) -> str:
    """Fetch OHLCV time series from info service. Returns the same string format as vendor get_ticker_data."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"start_date": start_date, "end_date": end_date}
    data = _get(None, base_url, f"/api/data/ticker-data/{ticker.upper()}", params=params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return str(data)


def get_stock_data(ticker: str, start_date: str, end_date: str, base_url: Optional[str] = None) -> str:
    """Backward-compatible alias for get_ticker_data."""
    return get_ticker_data(ticker=ticker, start_date=start_date, end_date=end_date, base_url=base_url)


def get_fundamentals(ticker: str, base_url: Optional[str] = None) -> str:
    """Fetch fundamentals from info service. Returns JSON string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    data = _get(None, base_url, f"/api/data/fundamentals/{ticker.upper()}", timeout=90)
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


def get_events(
    ticker: str,
    lookback_days: int = 10,
    base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch deterministic ticker events from /api/data/events/{ticker}."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        data = _get(
            None,
            base_url,
            f"/api/data/events/{ticker.upper()}",
            params={"lookback_days": lookback_days},
        )
        return data if isinstance(data, dict) else None
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
        # Backend fetches SEC docs + runs LLM extraction; can exceed 30s for large 10-Ks (e.g. GOOG)
        data = _get(None, base_url, f"/api/data/edgar-filing-content/{ticker.upper()}", params=params, timeout=120)
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

def get_edgar_full_text(
    ticker: str,
    form: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get complete SEC filing text for exploration (calls existing endpoint with raw=true).
    
    Returns:
        {
            "ticker": str,
            "filing": {"form": str, "filing_date": str, "accession_number": str},
            "text": str,
            "char_count": int,
            "error": str | None
        }
    """
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    
    params: Dict[str, Any] = {"limit": 1, "raw": "true"}  # Use existing endpoint with raw=true
    if form:
        params["form"] = form
    
    try:
        data = _get(
            None,
            base_url,
            f"/api/data/edgar-filing-content/{ticker.upper()}",
            params=params,
            timeout=60,
        )
    except Exception as e:
        return {
            "ticker": ticker,
            "filing": None,
            "text": "",
            "char_count": 0,
            "error": str(e),
        }
    
    if isinstance(data, dict) and data.get("filings"):
        filing = data["filings"][0]
        return {
            "ticker": ticker,
            "filing": {
                "form": filing.get("form"),
                "filing_date": filing.get("filing_date"),
                "accession_number": filing.get("accession_number"),
            },
            "text": filing.get("text", ""),
            "char_count": filing.get("char_count", 0),
            "error": None,
        }
    
    return {
        "ticker": ticker,
        "filing": None,
        "text": "",
        "char_count": 0,
        "error": data.get("error", "No filing available"),
    }



def get_market_movers(count: int = 8, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Fetch daily top gainers and losers (US market) from info service.
    Returns dict with 'gainers' and 'losers' lists of quote-like dicts."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    data = _get(None, base_url, "/api/data/market-movers", params={"count": count})
    if isinstance(data, dict):
        return data
    return {"gainers": [], "losers": []}


def get_reports(
    ticker: str,
    date: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch reports for a ticker from /api/data/reports/{ticker}. Auth required.
    Returns dict with report_run_id, report_date, reports (or None if not found)."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        params: Dict[str, str] = {}
        if date:
            params["date"] = date
        path = f"/api/data/reports/{ticker.upper()}"
        return _get(None, base_url, path, params=params if params else None)
    except Exception:
        return None


def get_reports_batch(
    tickers: List[str],
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch latest reports for multiple tickers via POST /api/data/reports/batch.
    Auth required. Returns {tickers: {ticker: {report_run_id, report_date, reports}}}."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    if requests is None:
        raise RuntimeError("requests is required; install with: pip install requests")
    ticker_list = [str(t).strip().upper() for t in tickers if t][:50]
    if not ticker_list:
        return {"tickers": {}}
    url = urljoin(base_url.rstrip("/") + "/", "api/data/reports/batch")
    r = requests.post(url, json={"tickers": ticker_list}, timeout=30)
    r.raise_for_status()
    out = r.json()
    return out if isinstance(out, dict) else {"tickers": {}}


def get_report_dates(ticker: str, base_url: Optional[str] = None) -> List[str]:
    """List report dates for a ticker from /api/data/reports/{ticker}/dates.
    Auth required. Returns list of date strings (newest first)."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return []
    try:
        data = _get(None, base_url, f"/api/data/reports/{ticker.upper()}/dates")
        if isinstance(data, dict) and "dates" in data:
            return data["dates"] or []
        return []
    except Exception:
        return []


def is_configured() -> bool:
    """Return True if info service URL is set."""
    return _get_info_service_base_url() is not None


def require_info_service() -> None:
    """Raise if INFO_SERVICE_URL is not set. Call at tool/graph init for fail-fast."""
    if _get_info_service_base_url() is None:
        raise ValueError(
            "INFO_SERVICE_URL (or config info_service_url) must be set. "
            "Agents work only with the backend."
        )


def get_indicators(
    ticker: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
    base_url: Optional[str] = None,
) -> str:
    """Fetch technical indicators from info service. Returns formatted string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"indicator": indicator, "curr_date": curr_date, "look_back_days": look_back_days}
    data = _get(None, base_url, f"/api/data/indicators/{ticker.upper()}", params=params, timeout=90)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return str(data)


def get_global_news(
    curr_date: str,
    lookback_days: int = 7,
    limit: int = 10,
    query: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    """Fetch global/macro news from info service. Returns formatted string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params: Dict[str, Any] = {"curr_date": curr_date, "lookback_days": lookback_days, "limit": limit}
    if query:
        params["query"] = query
    data = _get(None, base_url, "/api/data/global-news", params=params, timeout=90)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return str(data)


def get_insider_sentiment(
    ticker: str,
    curr_date: str,
    base_url: Optional[str] = None,
) -> str:
    """Fetch insider sentiment from info service. Returns formatted string."""
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        raise ValueError("Info service URL not configured (set INFO_SERVICE_URL or config info_service_url)")
    params = {"curr_date": curr_date}
    data = _get(None, base_url, f"/api/data/insider-sentiment/{ticker.upper()}", params=params)
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return str(data)


def get_polymarket_sentiment(ticker: str, base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch aggregated Polymarket prediction-market sentiment for a ticker from info service.

    Calls GET /api/polymarket/ticker/{ticker}. Returns the aggregated dict:
        {
            "ticker": str,
            "overall_sentiment": float,   # 0 (bearish) .. 0.5 (neutral) .. 1 (bullish)
            "confidence": float,          # 0..1, higher = more trading volume
            "trend": str,                 # "bullish" | "neutral" | "bearish"
            "narratives": dict,
            "top_markets": list[dict],    # question, probability, change_24h, volume, url, ...
            "market_count": int,
            "last_updated": str,
            "error": str | None,
        }
    Returns None if the service is not configured or the request fails.
    """
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        data = _get(None, base_url, f"/api/polymarket/ticker/{ticker.upper()}", timeout=90)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_market_rates(base_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch current market rates (treasury yields, risk-free rate) from info service.
    
    Returns:
        Dictionary with market rates:
        {
            "risk_free_rate": float,  # 10-year treasury (standard for WACC)
            "treasury_10y": float,
            "treasury_2y": float,
            "treasury_3m": float,
            "last_updated": str (ISO format),
            "source": "FRED",
            "cache_age_hours": float
        }
        
        Returns None if service not configured or error occurs.
    """
    base_url = base_url or _get_info_service_base_url()
    if not base_url:
        return None
    try:
        return _get(None, base_url, "/api/data/market-rates")
    except Exception:
        return None

"""
Build figure data and payload for portfolio report HTML (Vega-Lite).
Uses watchlist fetch_figure_data when backend is on path, or INFO_SERVICE_URL HTTP.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import urllib.request
import urllib.parse
import json


def _fetch_via_http(base_url: str, path: str, params: Optional[Dict[str, str]] = None) -> Any:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        ct = resp.headers.get("Content-Type", "")
        body = resp.read().decode()
        if "application/json" in ct:
            return json.loads(body)
        return body


def fetch_figure_data_via_http(tickers: List[str], base_url: str) -> Dict[str, Dict[str, Any]]:
    """Fetch historical and financial_charts per ticker via INFO_SERVICE_URL."""
    result: Dict[str, Dict[str, Any]] = {}
    for ticker in tickers:
        t = ticker.upper()
        result[t] = {}
        try:
            hist = _fetch_via_http(base_url, f"/api/data/historical/{t}", {"period": "6mo", "interval": "1d"})
            if isinstance(hist, dict):
                result[t]["historical"] = hist
            else:
                result[t]["historical"] = {"ticker": t, "data": [], "error": "unexpected response"}
        except Exception as e:
            result[t]["historical"] = {"ticker": t, "data": [], "count": 0, "error": str(e)}
        try:
            fc = _fetch_via_http(base_url, f"/api/data/financial-charts/{t}", {"freq": "annual"})
            if isinstance(fc, dict):
                result[t]["financial_charts"] = fc
            else:
                result[t]["financial_charts"] = {"ticker": t, "error": "unexpected response"}
        except Exception as e:
            result[t]["financial_charts"] = {"ticker": t, "error": str(e)}
    return result


def build_figure_data_and_payload(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Build figure_data (by_ticker: historical, financial_charts) and payload (entries for vega_specs).
    Uses watchlist fetch_figure_data when backend is on path, else INFO_SERVICE_URL HTTP.
    """
    config = config or {}
    conf = config.get("configurable") or {}
    info_url = conf.get("info_service_url") or os.environ.get("INFO_SERVICE_URL", "").strip().rstrip("/")
    figure_data: Dict[str, Dict[str, Any]] = {}

    if info_url:
        figure_data = fetch_figure_data_via_http(tickers, info_url)
    else:
        # Platform (INFO_SERVICE_URL) required; no yfinance fallback
        for t in tickers:
            figure_data[t.upper()] = {}

    entries: List[Dict[str, Any]] = []
    for ticker in tickers:
        t = ticker.upper()
        entry: Dict[str, Any] = {
            "ticker": t,
            "name": t,
            "report_date": None,
            "recommendation": "—",
            "confidence": None,
            "key_takeaways": [],
            "score": None,
            "score_label": None,
            "expected_return_pct": None,
            "bear_case_return_pct": None,
            "bull_case_return_pct": None,
            "quote": {"current_price": None, "daily_change_percent": None},
        }
        rep = existing_reports.get(t) or {}
        reports = rep.get("reports") or {}
        if isinstance(reports, dict):
            ftd = reports.get("final_trade_decision") or {}
            tip = reports.get("investment_plan") or {}
            if ftd.get("recommendation"):
                entry["recommendation"] = ftd.get("recommendation", "—")
            elif tip.get("recommendation"):
                entry["recommendation"] = tip.get("recommendation", "—")
            entry["expected_return_pct"] = ftd.get("expected_return_pct") or tip.get("expected_return_pct")
            entry["bear_case_return_pct"] = ftd.get("bear_case_return_pct") or tip.get("bear_case_return_pct")
            entry["bull_case_return_pct"] = ftd.get("bull_case_return_pct") or tip.get("bull_case_return_pct")
        entries.append(entry)

    payload = {"user": {}, "tickers": tickers, "entries": entries}
    return figure_data, payload

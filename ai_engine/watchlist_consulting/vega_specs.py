"""
Build Vega-Lite spec dicts for the watchlist report:
- Summary charts from payload (recommendation distribution, daily % change by ticker, return range)
- Market figure: price series from historical data
- Fundamentals figures: from financial_charts (e.g. revenue, EPS)
"""

from __future__ import annotations

from typing import Any, Dict, List

VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def recommendation_bar_spec(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bar chart: count of BUY / SELL / HOLD across the watchlist."""
    rec_counts: Dict[str, int] = {}
    for e in entries:
        r = (e.get("recommendation") or "HOLD").upper()
        if r not in ("BUY", "SELL", "HOLD"):
            r = "HOLD"
        rec_counts[r] = rec_counts.get(r, 0) + 1
    data = [{"recommendation": k, "count": v} for k, v in rec_counts.items()]
    if not data:
        data = [{"recommendation": "HOLD", "count": 0}]
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": "Recommendation distribution",
        "data": {"values": data},
        "mark": "bar",
        "encoding": {
            "x": {"field": "recommendation", "type": "nominal", "sort": ["BUY", "HOLD", "SELL"]},
            "y": {"field": "count", "type": "quantitative"},
            "color": {
                "field": "recommendation",
                "type": "nominal",
                "scale": {"range": ["#22c55e", "#eab308", "#ef4444"]},
                "sort": ["BUY", "HOLD", "SELL"],
            },
        },
        "width": 300,
        "height": 200,
    }


def daily_change_bar_spec(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bar chart: daily % change by ticker."""
    data = []
    for e in entries:
        ticker = e.get("ticker") or ""
        qt = e.get("quote") or {}
        pct = qt.get("daily_change_percent")
        if pct is None:
            continue
        try:
            data.append({"ticker": ticker, "daily_change_pct": float(pct)})
        except (TypeError, ValueError):
            pass
    if not data:
        return {
            "$schema": VEGA_LITE_SCHEMA,
            "title": "Daily % change",
            "data": {"values": [{"ticker": "—", "daily_change_pct": 0}]},
            "mark": "bar",
            "encoding": {"x": {"field": "ticker"}, "y": {"field": "daily_change_pct", "type": "quantitative"}},
            "width": 400,
            "height": 220,
        }
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": "Daily % change by ticker",
        "data": {"values": data},
        "mark": "bar",
        "encoding": {
            "x": {"field": "ticker", "type": "nominal", "sort": "-y"},
            "y": {"field": "daily_change_pct", "type": "quantitative", "title": "Daily change (%)"},
            "color": {
                "condition": {"test": "datum.daily_change_pct >= 0", "value": "#22c55e"},
                "value": "#ef4444",
            },
        },
        "width": max(300, min(500, len(data) * 50)),
        "height": 220,
    }


def return_range_spec(entries: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Horizontal bar or point chart: expected return (bear/base/bull) by ticker. Omit if no return data."""
    data = []
    for e in entries:
        ticker = e.get("ticker") or ""
        bear = e.get("bear_case_return_pct")
        base = e.get("expected_return_pct")
        bull = e.get("bull_case_return_pct")
        if bear is None and base is None and bull is None:
            continue
        if base is not None:
            data.append({"ticker": ticker, "return_pct": float(base), "scenario": "Expected"})
        if bear is not None:
            data.append({"ticker": ticker, "return_pct": float(bear), "scenario": "Bear"})
        if bull is not None:
            data.append({"ticker": ticker, "return_pct": float(bull), "scenario": "Bull"})
    if not data:
        return None
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": "Expected return % (Bear / Base / Bull)",
        "data": {"values": data},
        "mark": "point",
        "encoding": {
            "y": {"field": "ticker", "type": "nominal"},
            "x": {"field": "return_pct", "type": "quantitative", "title": "Return %"},
            "color": {"field": "scenario", "type": "nominal"},
            "shape": {"field": "scenario", "type": "nominal"},
        },
        "width": 400,
        "height": max(150, len(set(d["ticker"] for d in data)) * 28),
    }


def price_series_spec(ticker: str, historical: Dict[str, Any]) -> Dict[str, Any] | None:
    """Line chart: OHLCV close price over time (market analysis figure)."""
    raw = historical.get("data") or []
    if not raw:
        return None
    values = []
    for row in raw:
        date_val = row.get("date")
        close = row.get("close")
        if date_val is not None and close is not None:
            values.append({"date": date_val, "close": float(close)})
    if not values:
        return None
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": f"{ticker} price",
        "data": {"values": values},
        "mark": "line",
        "encoding": {
            "x": {"field": "date", "type": "temporal", "title": "Date"},
            "y": {"field": "close", "type": "quantitative", "title": "Close"},
        },
        "width": 400,
        "height": 220,
    }


def fundamentals_bar_spec(
    ticker: str,
    financial_charts: Dict[str, Any],
    series_key: str,
    title: str | None = None,
) -> Dict[str, Any] | None:
    """Bar chart for one fundamental series from financial_charts (e.g. historical_financials.revenue, .eps)."""
    hf = financial_charts.get("historical_financials")
    if not hf or not isinstance(hf, dict):
        return None
    periods = hf.get("periods") or []
    values_list = hf.get(series_key)
    if not periods or not values_list or len(values_list) != len(periods):
        return None
    values = [{"period": str(p), "value": v} for p, v in zip(periods, values_list) if v is not None]
    if not values:
        return None
    label = {"revenue": "Revenue", "eps": "EPS", "operating_income": "Operating Income"}.get(series_key, series_key)
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": title or f"{ticker} {label}",
        "data": {"values": values},
        "mark": "bar",
        "encoding": {
            "x": {"field": "period", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative"},
        },
        "width": 360,
        "height": 200,
    }


def build_all_specs(
    payload: Dict[str, Any],
    figure_data: Dict[str, Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Build a list of Vega-Lite specs for the report.
    - Summary: recommendation bar, daily change bar, return range (if data)
    - Per-ticker: price series from figure_data["ticker"]["historical"], optional fundamentals from financial_charts
    """
    specs: List[Dict[str, Any]] = []
    entries = payload.get("entries") or []
    figure_data = figure_data or {}

    specs.append(recommendation_bar_spec(entries))
    specs.append(daily_change_bar_spec(entries))
    ret_spec = return_range_spec(entries)
    if ret_spec:
        specs.append(ret_spec)

    for e in entries:
        ticker = e.get("ticker")
        if not ticker:
            continue
        fd = figure_data.get(ticker) or {}
        hist = fd.get("historical")
        if hist and hist.get("data"):
            ps = price_series_spec(ticker, hist)
            if ps:
                specs.append(ps)
        charts = fd.get("financial_charts")
        if charts and not charts.get("error"):
            hf = charts.get("historical_financials")
            if hf and isinstance(hf, dict):
                for key in ("revenue", "eps"):
                    fs = fundamentals_bar_spec(ticker, charts, key, title=f"{ticker} {key.capitalize()}")
                    if fs:
                        specs.append(fs)
                        break

    return specs

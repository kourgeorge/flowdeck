"""
Stage 6: Data Builder Agent.
Input: figure_plan, data_jobs, watchlist_payload (tickers).
Output: figure_data (figure_id -> chart-ready dataset), data_quality_notes.
Reuses fetch_figure_data; adds volatility/drawdown from historical and sector/industry from company info.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_schemas import DataJob, FigurePlanItem

try:
    from fetch_figure_data import fetch_figure_data_for_tickers
    from services.info_fetcher import get_info_fetcher
except ImportError:
    fetch_figure_data_for_tickers = None  # type: ignore
    get_info_fetcher = None  # type: ignore


def _volatility_from_historical(historical: Dict[str, Any]) -> Optional[float]:
    """Simple vol proxy: std of daily returns from close. Returns None if insufficient data."""
    data = historical.get("data") or []
    if len(data) < 2:
        return None
    closes = []
    for row in data:
        c = row.get("close")
        if c is not None:
            closes.append(float(c))
    if len(closes) < 2:
        return None
    rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    mean_ret = sum(rets) / len(rets)
    var = sum((r - mean_ret) ** 2 for r in rets) / len(rets)
    return (var ** 0.5) * 100.0  # as percentage


def _run_data_jobs(
    data_jobs: List[DataJob],
    payload: Dict[str, Any],
) -> tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Execute data_jobs and return by_ticker raw data plus quality notes."""
    by_ticker: Dict[str, Dict[str, Any]] = {}
    notes: List[str] = []

    tickers_all = list({t for j in data_jobs for t in j.tickers})
    if not tickers_all:
        return by_ticker, notes

    if fetch_figure_data_for_tickers:
        try:
            raw = fetch_figure_data_for_tickers(
                tickers_all,
                include_historical=True,
                include_fundamentals=False,
                include_financial_charts=True,
                historical_period="6mo",
            )
            for t, data in raw.items():
                by_ticker[t] = data
                if data.get("historical", {}).get("error"):
                    notes.append(f"{t}: historical error")
                if data.get("financial_charts", {}).get("error"):
                    notes.append(f"{t}: financial_charts missing or error")
        except Exception as e:
            notes.append(f"fetch_figure_data error: {e}")

    # Sector/industry from company info
    if get_info_fetcher:
        try:
            fetcher = get_info_fetcher()
            for t in tickers_all:
                t = t.upper()
                if t not in by_ticker:
                    by_ticker[t] = {}
                try:
                    info = fetcher.get_company_info(t)
                    by_ticker[t]["sector"] = info.get("sector", "N/A")
                    by_ticker[t]["industry"] = info.get("industry", "N/A")
                except Exception:
                    by_ticker[t]["sector"] = "N/A"
                    by_ticker[t]["industry"] = "N/A"
        except Exception as e:
            notes.append(f"company_info fetch: {e}")

    # Volatility from historical
    for t, data in by_ticker.items():
        hist = data.get("historical") or {}
        if hist and not hist.get("error"):
            vol = _volatility_from_historical(hist)
            if vol is not None:
                by_ticker[t]["volatility_pct"] = round(vol, 2)

    return by_ticker, notes


def run_data_builder(
    figure_plan: List[FigurePlanItem],
    data_jobs: List[DataJob],
    watchlist_payload: Dict[str, Any],
) -> tuple[Dict[str, Any], List[str]]:
    """
    Execute data_jobs, build figure_data keyed by figure_id (and by_ticker for legacy specs).
    Returns (figure_data, data_quality_notes).
    """
    entries = watchlist_payload.get("entries") or []
    by_ticker, data_quality_notes = _run_data_jobs(data_jobs, watchlist_payload)

    figure_data: Dict[str, Any] = {}
    # Legacy key for existing vega_specs.build_all_specs(payload, figure_data)
    figure_data["by_ticker"] = by_ticker

    # recommendation_dist
    rec_counts: Dict[str, int] = {}
    for e in entries:
        r = (e.get("recommendation") or "HOLD").upper()
        if r not in ("BUY", "SELL", "HOLD"):
            r = "HOLD"
        rec_counts[r] = rec_counts.get(r, 0) + 1
    figure_data["recommendation_dist"] = {"values": [{"recommendation": k, "count": v} for k, v in rec_counts.items()]}

    # daily_change
    daily_vals = []
    for e in entries:
        ticker = e.get("ticker")
        qt = e.get("quote") or {}
        pct = qt.get("daily_change_percent")
        if ticker and pct is not None:
            try:
                daily_vals.append({"ticker": ticker, "daily_change_pct": float(pct)})
            except (TypeError, ValueError):
                pass
    figure_data["daily_change"] = {"values": daily_vals if daily_vals else [{"ticker": "—", "daily_change_pct": 0}]}

    # return_range
    ret_vals = []
    for e in entries:
        ticker = e.get("ticker") or ""
        bear = e.get("bear_case_return_pct")
        base = e.get("expected_return_pct")
        bull = e.get("bull_case_return_pct")
        if base is not None:
            ret_vals.append({"ticker": ticker, "return_pct": float(base), "scenario": "Expected"})
        if bear is not None:
            ret_vals.append({"ticker": ticker, "return_pct": float(bear), "scenario": "Bear"})
        if bull is not None:
            ret_vals.append({"ticker": ticker, "return_pct": float(bull), "scenario": "Bull"})
    figure_data["return_range"] = {"values": ret_vals}

    # risk_return_scatter: expected return vs volatility, color by sector
    scatter_vals = []
    for e in entries:
        ticker = (e.get("ticker") or "").upper()
        base = e.get("expected_return_pct")
        td = by_ticker.get(ticker) or {}
        vol = td.get("volatility_pct")
        sector = td.get("sector", "N/A")
        if base is not None:
            scatter_vals.append({
                "ticker": ticker,
                "expected_return_pct": float(base),
                "volatility_pct": vol,
                "sector": sector,
            })
    figure_data["risk_return_scatter"] = {"values": scatter_vals}

    # sector_exposure
    sector_counts: Dict[str, int] = {}
    industry_counts: Dict[str, int] = {}
    for t, td in by_ticker.items():
        s = td.get("sector", "N/A")
        i = td.get("industry", "N/A")
        sector_counts[s] = sector_counts.get(s, 0) + 1
        industry_counts[i] = industry_counts.get(i, 0) + 1
    figure_data["sector_exposure"] = {"sector_counts": sector_counts, "industry_counts": industry_counts}

    # theme_map: filled by conductor from theme_output when building specs (or leave placeholder)
    figure_data["theme_map"] = {"values": []}

    # price_small_multiples: per-ticker historical under by_ticker already; reference same
    figure_data["price_small_multiples"] = {"by_ticker": by_ticker}

    # fundamentals_trajectory: per-ticker financial_charts under by_ticker
    figure_data["fundamentals_trajectory"] = {"by_ticker": by_ticker}

    return figure_data, data_quality_notes

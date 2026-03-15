#!/usr/bin/env python3
"""
Test regional-view tickers for range data (1W, 1M, 6M, YTD).

Three sources:
  - yfinance (default): direct MarketDataService (batch + retry, 1-row ok).
  - yahooquery: direct yahooquery Ticker().history(period=..., interval='1d').
  - backend: HTTP GET /api/data/market-overview (live backend).

Uses the same international ticker list as the API (data_layer.constants.MARKET_OVERVIEW_TICKERS)
for yfinance/yahooquery; for backend, ticker list comes from the API response.
Reports how many tickers do NOT return proper values per range and lists them.

Usage (from repo root):
    PYTHONPATH=backend python scripts/test_regional_yahoo_ranges.py
    PYTHONPATH=backend python scripts/test_regional_yahoo_ranges.py --yahooquery
    PYTHONPATH=backend python scripts/test_regional_yahoo_ranges.py --backend
    FLOWDECK_API_URL=http://localhost:8002 python scripts/test_regional_yahoo_ranges.py --backend
"""

import argparse
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Allow importing backend services when run from repo root
_repo_root = Path(__file__).resolve().parent.parent
_backend = _repo_root / "backend"
if _backend.is_dir() and str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

# Range -> period for yahooquery (yfinance/backend use MarketDataService.MARKET_RANGE_PERIODS; 1w uses 5d there too)
YAHOOQUERY_PERIOD = {"1w": "5d", "1mo": "1mo", "6mo": "6mo", "ytd": "ytd"}
OFFSET_SESSIONS = {"1w": 6, "1mo": 22, "6mo": 126, "ytd": None}  # None = use first row of year


def get_regional_tickers() -> list[str]:
    """Same ticker list the backend uses for market overview 'international' (regions)."""
    from data_layer.constants import MARKET_OVERVIEW_TICKERS

    tickers = []
    seen = set()
    for group_key, ticker, _name in MARKET_OVERVIEW_TICKERS:
        if group_key != "international":
            continue
        t = ticker.upper()
        if t not in seen:
            seen.add(t)
            tickers.append(t)
    return tickers


def _is_valid_price(price: float) -> bool:
    try:
        p = float(price)
        return p > 0 and not math.isnan(p) and not math.isinf(p)
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fetch_with_yahooquery(
    tickers: list[str],
    range_: str,
) -> dict[str, Optional[dict[str, Any]]]:
    """Fetch quotes for range using yahooquery Ticker().history(). Returns ticker -> {current_price, changePercent} or None."""
    try:
        from yahooquery import Ticker
    except ImportError:
        print("yahooquery not installed. Install with: pip install yahooquery", file=sys.stderr)
        return {t: None for t in tickers}

    period = YAHOOQUERY_PERIOD.get(range_, "1mo")
    offset = OFFSET_SESSIONS.get(range_)
    results: dict[str, Optional[dict[str, Any]]] = {t: None for t in tickers}

    # yahooquery accepts space-separated symbols or list
    batch_size = 25
    for i in range(0, len(tickers), batch_size):
        chunk = tickers[i : i + batch_size]
        try:
            tq = Ticker(chunk)
            df = tq.history(period=period, interval="1d")
            if df is None or df.empty:
                continue
            # MultiIndex (symbol, date) or single symbol -> index is just date
            if hasattr(df.index, "levels") and len(df.index.names) >= 2:
                # MultiIndex: (symbol, date); level 0 may be lower or mixed case
                level0 = df.index.get_level_values(0)
                sym_to_key = {str(s).upper(): s for s in level0.unique()}
                for sym in chunk:
                    try:
                        key = sym_to_key.get(sym.upper()) or sym_to_key.get(sym)
                        if key is None:
                            continue
                        close_series = df.xs(key, level=0)["close"].dropna()
                        if close_series.empty:
                            continue
                        current = _safe_float(close_series.iloc[-1])
                        if current is None or not _is_valid_price(current):
                            continue
                        if len(close_series) >= 2 and offset is not None:
                            prev = (
                                _safe_float(close_series.iloc[-offset])
                                if len(close_series) >= offset
                                else _safe_float(close_series.iloc[0])
                            )
                        elif len(close_series) >= 2 and offset is None:
                            # YTD: first close of current year
                            from datetime import datetime

                            yr = datetime.now().year
                            prev = None
                            for j in range(len(close_series)):
                                idx = close_series.index[j]
                                if hasattr(idx, "year") and idx.year == yr:
                                    prev = _safe_float(close_series.iloc[j])
                                    break
                            if prev is None:
                                prev = _safe_float(close_series.iloc[0])
                        else:
                            prev = current
                        if prev is None or not _is_valid_price(prev) or prev <= 0:
                            prev = current
                        change_pct = (current - prev) / prev * 100 if prev else 0.0
                        results[sym] = {
                            "current_price": round(current, 2),
                            "changePercent": round(change_pct, 2),
                        }
                    except Exception:
                        continue
            else:
                # Single-symbol result: index is date
                if len(chunk) != 1:
                    continue
                sym = chunk[0]
                try:
                    close_series = df["close"].dropna() if "close" in df.columns else None
                    if close_series is None or close_series.empty:
                        continue
                    current = _safe_float(close_series.iloc[-1])
                    if current is None or not _is_valid_price(current):
                        continue
                    if len(close_series) >= 2 and offset is not None:
                        prev = (
                            _safe_float(close_series.iloc[-offset])
                            if len(close_series) >= offset
                            else _safe_float(close_series.iloc[0])
                        )
                    elif len(close_series) >= 2 and offset is None:
                        from datetime import datetime

                        yr = datetime.now().year
                        prev = None
                        for j in range(len(close_series)):
                            idx = close_series.index[j]
                            if hasattr(idx, "year") and idx.year == yr:
                                prev = _safe_float(close_series.iloc[j])
                                break
                        if prev is None:
                            prev = _safe_float(close_series.iloc[0])
                    else:
                        prev = current
                    if prev is None or not _is_valid_price(prev) or prev <= 0:
                        prev = current
                    change_pct = (current - prev) / prev * 100 if prev else 0.0
                    results[sym] = {
                        "current_price": round(current, 2),
                        "changePercent": round(change_pct, 2),
                    }
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: yahooquery batch failed for chunk: {e}", file=sys.stderr)

    # Retry missing one-by-one
    missing = [t for t in tickers if results[t] is None]
    for t in missing:
        try:
            tq = Ticker(t)
            df = tq.history(period=period if range_ != "ytd" else "3mo", interval="1d")
            if df is None or df.empty:
                continue
            close_series = df["close"].dropna() if "close" in df.columns else None
            if close_series is None or close_series.empty:
                continue
            current = _safe_float(close_series.iloc[-1])
            if current is None or not _is_valid_price(current):
                continue
            if len(close_series) >= 2 and offset is not None:
                prev = (
                    _safe_float(close_series.iloc[-offset])
                    if len(close_series) >= offset
                    else _safe_float(close_series.iloc[0])
                )
            elif len(close_series) >= 2 and offset is None:
                from datetime import datetime

                yr = datetime.now().year
                prev = None
                for j in range(len(close_series)):
                    idx = close_series.index[j]
                    if hasattr(idx, "year") and idx.year == yr:
                        prev = _safe_float(close_series.iloc[j])
                        break
                if prev is None:
                    prev = _safe_float(close_series.iloc[0])
            else:
                prev = current
            if prev is None or not _is_valid_price(prev) or prev <= 0:
                prev = current
            change_pct = (current - prev) / prev * 100 if prev else 0.0
            results[t] = {"current_price": round(current, 2), "changePercent": round(change_pct, 2)}
        except Exception:
            pass

    return results


def run_yfinance(tickers: list[str], ranges: tuple[str, ...]) -> dict[str, tuple[int, list[str]]]:
    """Use MarketDataService (same as backend). Returns range -> (valid_count, missing_list)."""
    from services.market_data_service import MarketDataService

    range_results: dict[str, tuple[int, list[str]]] = {}
    for range_ in ranges:
        quotes = MarketDataService.get_multiple_quotes_batch_with_range(tickers, range_)
        valid = sum(1 for q in quotes.values() if q is not None and q.current_price is not None)
        missing = [t for t in tickers if quotes.get(t) is None or quotes.get(t).current_price is None]
        range_results[range_] = (valid, missing)
    return range_results


def run_yahooquery(tickers: list[str], ranges: tuple[str, ...]) -> dict[str, tuple[int, list[str]]]:
    """Use yahooquery Ticker().history(). Returns range -> (valid_count, missing_list)."""
    range_results: dict[str, tuple[int, list[str]]] = {}
    for range_ in ranges:
        quotes = fetch_with_yahooquery(tickers, range_)
        valid = sum(
            1 for q in quotes.values() if q is not None and q.get("current_price") is not None
        )
        missing = [
            t
            for t in tickers
            if quotes.get(t) is None or quotes.get(t).get("current_price") is None
        ]
        range_results[range_] = (valid, missing)
    return range_results


def run_backend(
    base_url: str,
    ranges: tuple[str, ...],
) -> tuple[dict[str, tuple[int, list[str]]], list[str]]:
    """Fetch from backend GET /api/data/market-overview. Returns (range_results, tickers)."""
    try:
        import requests
    except ImportError:
        print("requests not installed. Install with: pip install requests", file=sys.stderr)
        return {}, []

    range_results: dict[str, tuple[int, list[str]]] = {}
    tickers: list[str] = []

    for range_ in ranges:
        url = f"{base_url.rstrip('/')}/api/data/market-overview"
        params = {
            "limit_indices": 1,
            "offset_indices": 0,
            "limit_sectors": 1,
            "offset_sectors": 0,
            "limit_regions": 100,
            "offset_regions": 0,
            "limit_commodities": 1,
            "offset_commodities": 0,
            "range": range_,
        }
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Warning: backend request failed for range {range_}: {e}", file=sys.stderr)
            range_results[range_] = (0, [])
            continue

        international = data.get("international") or []
        if not tickers:
            tickers = [item.get("ticker", "").strip() for item in international if item.get("ticker")]
        valid = sum(
            1
            for item in international
            if item.get("price") is not None
        )
        missing = [
            item.get("ticker", "").strip()
            for item in international
            if item.get("price") is None
        ]
        range_results[range_] = (valid, missing)

    return range_results, tickers


def _summary_for_source(
    range_results: dict[str, tuple[int, list[str]]],
    total: int,
) -> tuple[list[tuple[int, int]], set[str]]:
    """Return (per-range (valid, total), set of tickers missing in at least one range)."""
    ranges_order = ("1w", "1mo", "6mo", "ytd")
    per_range: list[tuple[int, int]] = []
    all_missing: set[str] = set()
    for range_ in ranges_order:
        valid, missing_list = range_results.get(range_, (0, []))
        n = valid + len(missing_list)
        total_n = n if n else total
        per_range.append((valid, total_n))
        all_missing.update(missing_list)
    return per_range, all_missing


def run_compare(
    tickers: list[str],
    ranges: tuple[str, ...],
    backend_url: str,
) -> None:
    """Run all three sources and print a comparison table."""
    total = len(tickers)
    print("Comparing all 3 sources (yfinance, yahooquery, backend)")
    print(f"  Ticker list: {total} international (MARKET_OVERVIEW_TICKERS)")
    print(f"  Backend URL: {backend_url}")
    print()

    t0 = time.perf_counter()
    results_yf = run_yfinance(tickers, ranges)
    time_yf = time.perf_counter() - t0

    t0 = time.perf_counter()
    results_yq = run_yahooquery(tickers, ranges)
    time_yq = time.perf_counter() - t0

    t0 = time.perf_counter()
    results_be, tickers_be = run_backend(backend_url, ranges)
    time_be = time.perf_counter() - t0
    total_be = len(tickers_be)

    # Table header (with Time column)
    print(f"  {'Source':<12} │ {'1W':>8} │ {'1MO':>8} │ {'6MO':>8} │ {'YTD':>8} │ Any missing │ {'Time':>10}")
    print("  " + "─" * 12 + "─┼" + "─" * 10 + "┼" + "─" * 10 + "┼" + "─" * 10 + "┼" + "─" * 10 + "┼" + "─" * 12 + "┼" + "─" * 12)

    def row(name: str, range_results: dict, tot: int, elapsed: float) -> None:
        per_range, any_missing = _summary_for_source(range_results, tot)
        cells = [f"{v}/{t}" for v, t in per_range]
        missing_str = f"{len(any_missing)}" if any_missing else "0"
        time_str = f"{elapsed:.1f}s"
        print(f"  {name:<12} │ {cells[0]:>8} │ {cells[1]:>8} │ {cells[2]:>8} │ {cells[3]:>8} │ {missing_str:>12} │ {time_str:>10}")

    row("yfinance", results_yf, total, time_yf)
    row("yahooquery", results_yq, total, time_yq)
    row("backend", results_be, total_be, time_be)

    print()
    # Per-range comparison
    print("  Per range (valid/total):")
    for i, range_ in enumerate(ranges):
        v_yf, t_yf = _summary_for_source(results_yf, total)[0][i]
        v_yq, t_yq = _summary_for_source(results_yq, total)[0][i]
        v_be, t_be = _summary_for_source(results_be, total_be)[0][i]
        print(f"    {range_.upper():>3}:  yfinance {v_yf}/{t_yf}  |  yahooquery {v_yq}/{t_yq}  |  backend {v_be}/{t_be}")

    # Tickers missing in one source but not another
    _, miss_yf = _summary_for_source(results_yf, total)
    _, miss_yq = _summary_for_source(results_yq, total)
    _, miss_be = _summary_for_source(results_be, total_be)
    only_yf = miss_yf - miss_yq - miss_be
    only_yq = miss_yq - miss_yf - miss_be
    only_be = miss_be - miss_yf - miss_yq
    all_three = miss_yf & miss_yq & miss_be
    if only_yf or only_yq or only_be or (all_three and (miss_yf or miss_yq or miss_be)):
        print()
        print("  Missing only in yfinance:", sorted(only_yf) if only_yf else "—")
        print("  Missing only in yahooquery:", sorted(only_yq) if only_yq else "—")
        print("  Missing only in backend:", sorted(only_be) if only_be else "—")
        if all_three:
            print("  Missing in all three:", sorted(all_three))
    print()
    print("Done. Backend uses same logic as yfinance (MarketDataService).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test regional tickers for 1W/1M/6M/YTD. Choose source: yfinance (default), yahooquery, backend, or --compare all."
    )
    parser.add_argument(
        "--yahooquery",
        "-y",
        action="store_true",
        help="Use yahooquery Ticker().history() instead of yfinance",
    )
    parser.add_argument(
        "--backend",
        "-b",
        action="store_true",
        help="Use live backend HTTP API (GET /api/data/market-overview)",
    )
    parser.add_argument(
        "--compare",
        "-c",
        action="store_true",
        help="Run all 3 sources (yfinance, yahooquery, backend) and print comparison table",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("FLOWDECK_API_URL", "http://localhost:8002"),
        help="Backend base URL when using --backend (default: FLOWDECK_API_URL or http://localhost:8002)",
    )
    args = parser.parse_args()

    ranges = ("1w", "1mo", "6mo", "ytd")

    if args.compare:
        tickers = get_regional_tickers()
        run_compare(tickers, ranges, args.url)
        return

    if args.backend:
        print("Regional map data test (backend HTTP API)")
        print(f"  URL: {args.url}")
        print("  GET /api/data/market-overview with limit_regions=100, range=1w|1mo|6mo|ytd")
        t0 = time.perf_counter()
        range_results, tickers = run_backend(args.url, ranges)
        elapsed = time.perf_counter() - t0
        total = len(tickers)
        print(f"  Tickers: {total} (from API international list)")
        print("  Ranges: 1W, 1M, 6M, YTD")
        print()
    else:
        tickers = get_regional_tickers()
        total = len(tickers)
        if args.yahooquery:
            print("Regional map data test (yahooquery)")
            print("  Source: yahooquery Ticker().history(period=..., interval='1d'), batch 25 + single-ticker retry")
        else:
            print("Regional map data test (yfinance)")
            print("  Source: MarketDataService (batch 25 + single-ticker retry, 1-row accepted as 0%% change)")
        print(f"  Tickers: {total} (international from MARKET_OVERVIEW_TICKERS)")
        print("  Ranges: 1W, 1M, 6M, YTD")
        print()
        t0 = time.perf_counter()
        if args.yahooquery:
            range_results = run_yahooquery(tickers, ranges)
        else:
            range_results = run_yfinance(tickers, ranges)
        elapsed = time.perf_counter() - t0

    for range_ in ranges:
        valid, missing = range_results[range_]
        n_missing = len(missing)
        pct = (valid / total * 100) if total else 0
        print(f"  {range_.upper():>3}: {valid:3}/{total} valid ({pct:5.1f}%)  —  not returning proper values: {n_missing:3}")
        if missing:
            print(f"       Missing: {', '.join(missing)}")

    # Summary: tickers that fail in at least one range
    all_missing_by_ticker: dict[str, list[str]] = {}
    for range_, (_valid, missing_list) in range_results.items():
        for t in missing_list:
            all_missing_by_ticker.setdefault(t, []).append(range_.upper())
    any_missing = sorted(all_missing_by_ticker.keys())
    n_any_missing = len(any_missing)

    print()
    print("Summary")
    print(f"  Tickers not returning proper values in at least one range: {n_any_missing}/{total}")
    if any_missing:
        print("  By ticker (ranges where missing):")
        for t in any_missing:
            ranges_where = ", ".join(all_missing_by_ticker[t])
            print(f"    {t}: {ranges_where}")
    if not args.compare:
        print(f"  Time: {elapsed:.1f}s")
    print()
    print("Done. 'Proper value' = non-None quote with current_price.")


if __name__ == "__main__":
    main()

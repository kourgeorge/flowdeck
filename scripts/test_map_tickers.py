#!/usr/bin/env python3
"""
Test tickers from the world map (WorldMapRegionalStocks) against the backend.

For each ticker on the map, calls GET /api/data/quote/{ticker} and reports
whether the backend returns data (200 + payload) or not (404 / error).

Usage:
    # Local backend (default)
    python scripts/test_map_tickers.py

    # Custom base URL
    FLOWDECK_API_URL=http://localhost:8000 python scripts/test_map_tickers.py
"""

import os
import sys
import requests

# Tickers from frontend WorldMapRegionalStocks REGION_COORDS (keys only)
MAP_TICKERS = [
    "^GSPC", "^DJI", "^RUT", "SPY", "DIA", "IWM", "MDY", "VOO", "VTI",
    "^IXIC", "^NDX", "QQQ", "^VIX",
    "^TA125.TA", "TA35.TA",
    "^TASI.SR", "KSA", "UAE", "QAT", "BAX", "KWT", "EGPT", "^CASE30",
    "MASI", "^NQMA",
    "^FTSE", "^GDAXI", "^FCHI", "^STOXX50E", "EWG", "EWU", "FTSEMIB.MI",
    "^IBEX", "^AEX", "^SSMI", "^OMXSPI", "WIG20.WA", "^ATX", "^BFX", "^OMXC20",
    "^OMXH25", "GD.AT", "FPXAA.PR", "EIRL",     "^OSEAX", "^BUX.BD",
    "IMOEX.ME",
    "^N225", "^HSI", "^STI", "^AXJO", "^KS11", "^TWII", "^BSESN", "^NSEI",
    "^JKSE", "^KLSE", "000001.SS", "^SET.BK", "PSEI.PS", "VNM", "XBAK.DE",
    "^NZ50", "ENZL", "EWJ", "FXI", "INDA", "EWM", "EIDO",
    "XU100.IS", "TUR",
    "^GSPTSE", "^BVSP", "^MXX", "^IPSA", "^MERV", "ICOLCAP.CL", "EPU", "IBC.CR",
    "EWC", "EWZ", "EWA",
    "^SPAFREP", "AFK", "^JN0U.JO", "EZA", "NGE", "FNKEN2.L", "FM",
    "EFA", "EEM", "VEA", "VWO",
]

BASE_URL = os.environ.get("FLOWDECK_API_URL", "http://localhost:8000")


def main() -> None:
    quote_url = f"{BASE_URL}/api/data/quote"
    ok = []
    not_found = []
    errors = []

    print(f"Testing {len(MAP_TICKERS)} map tickers against {quote_url}/{{ticker}}")
    print()

    for ticker in MAP_TICKERS:
        url = f"{quote_url}/{ticker}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data:
                    ok.append((ticker, data))
                else:
                    not_found.append((ticker, "empty body"))
            elif r.status_code == 404:
                not_found.append((ticker, "404"))
            else:
                errors.append((ticker, f"HTTP {r.status_code}"))
        except requests.RequestException as e:
            errors.append((ticker, str(e)))

    # Summary
    print(f"OK (got info):     {len(ok)}")
    print(f"Not found / empty: {len(not_found)}")
    print(f"Errors:            {len(errors)}")
    print()

    if not_found:
        print("Tickers with no info (404 or empty):")
        for t, reason in not_found:
            print(f"  {t}  ({reason})")
        print()

    if errors:
        print("Tickers with errors:")
        for t, msg in errors:
            print(f"  {t}: {msg}")
        print()

    if ok:
        print("Sample of tickers that returned data (first 5):")
        for ticker, data in ok[:5]:
            price = data.get("current_price")
            sym = data.get("ticker", ticker)
            print(f"  {ticker}: {sym}  price={price}")
        if len(ok) > 5:
            print(f"  ... and {len(ok) - 5} more.")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

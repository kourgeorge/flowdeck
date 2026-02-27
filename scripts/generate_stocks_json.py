#!/usr/bin/env python3
"""
Generate a comprehensive stocks.json for the frontend search.

Sources (in order of preference):
  1. yfinance screener / pandas_datareader  -- no API key needed
  2. SEC EDGAR company tickers JSON         -- free, no key, ~13k US-listed companies
  3. Fallback: hardcoded S&P 500 list

The script writes frontend/public/stocks.json with entries:
  [{"ticker": "AAPL", "name": "Apple Inc."}, ...]

Usage:
  python scripts/generate_stocks_json.py
  python scripts/generate_stocks_json.py --source edgar   # SEC EDGAR only
  python scripts/generate_stocks_json.py --source sp500   # S&P 500 only
  python scripts/generate_stocks_json.py --source nasdaq  # NASDAQ-listed via yfinance
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "frontend" / "public" / "stocks.json"


# ---------------------------------------------------------------------------
# Source 1: SEC EDGAR – all US-listed companies (~13 000 tickers, no API key)
# ---------------------------------------------------------------------------

def fetch_from_edgar() -> list[dict]:
    """
    Download the SEC EDGAR company tickers JSON.
    Returns list of {"ticker": ..., "name": ...} dicts.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    print(f"Fetching from SEC EDGAR: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "flowdeck/1.0 contact@example.com"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    stocks = []
    for entry in data.values():
        ticker = entry.get("ticker", "").strip().upper()
        name = entry.get("title", "").strip()
        if ticker and name and _is_valid_ticker(ticker):
            stocks.append({"ticker": ticker, "name": name})

    # Sort alphabetically by ticker
    stocks.sort(key=lambda x: x["ticker"])
    print(f"  → {len(stocks)} stocks from SEC EDGAR")
    return stocks


# ---------------------------------------------------------------------------
# Source 2: NASDAQ FTP – all NASDAQ + other-listed tickers
# ---------------------------------------------------------------------------

def fetch_from_nasdaq_ftp() -> list[dict]:
    """
    Download NASDAQ-listed and other-listed tickers from NASDAQ's FTP.
    Returns list of {"ticker": ..., "name": ...} dicts.
    """
    urls = [
        "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    ]
    stocks = {}
    for url in urls:
        print(f"Fetching from NASDAQ FTP: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                lines = resp.read().decode("utf-8", errors="replace").splitlines()
        except Exception as e:
            print(f"  Warning: could not fetch {url}: {e}")
            continue

        if not lines:
            continue

        # First line is header
        header = lines[0].split("|")
        try:
            sym_idx = header.index("Symbol")
            name_idx = header.index("Security Name") if "Security Name" in header else header.index("Security Name")
        except ValueError:
            # Try alternate column names
            sym_idx = 0
            name_idx = 1

        for line in lines[1:]:
            parts = line.split("|")
            if len(parts) <= max(sym_idx, name_idx):
                continue
            ticker = parts[sym_idx].strip().upper()
            name = parts[name_idx].strip()
            # Skip test issues, warrants, units, etc.
            if not ticker or not name or ticker == "SYMBOL" or "TEST" in ticker:
                continue
            if not _is_valid_ticker(ticker):
                continue
            stocks[ticker] = name

    result = [{"ticker": t, "name": n} for t, n in sorted(stocks.items())]
    print(f"  → {len(result)} stocks from NASDAQ FTP")
    return result


# ---------------------------------------------------------------------------
# Source 3: S&P 500 via Wikipedia (fallback, ~503 tickers)
# ---------------------------------------------------------------------------

def fetch_sp500() -> list[dict]:
    """Scrape S&P 500 constituents from Wikipedia."""
    try:
        import pandas as pd
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        print(f"Fetching S&P 500 from Wikipedia...")
        tables = pd.read_html(url)
        df = tables[0]
        stocks = []
        for _, row in df.iterrows():
            ticker = str(row["Symbol"]).strip().upper().replace(".", "-")
            name = str(row["Security"]).strip()
            if ticker and name:
                stocks.append({"ticker": ticker, "name": name})
        stocks.sort(key=lambda x: x["ticker"])
        print(f"  → {len(stocks)} S&P 500 stocks")
        return stocks
    except ImportError:
        print("  pandas not available, skipping Wikipedia S&P 500 source")
        return []
    except Exception as e:
        print(f"  Warning: could not fetch S&P 500: {e}")
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICKER_RE = re.compile(r'^[A-Z0-9]{1,6}(-[A-Z0-9]{1,2})?$')

def _is_valid_ticker(ticker: str) -> bool:
    """
    Accept standard US equity tickers.
    Only rejects clearly invalid entries: empty, containing spaces,
    or purely numeric strings.
    """
    if not ticker:
        return False
    if ' ' in ticker:
        return False
    if ticker.isdigit():
        return False
    return bool(_TICKER_RE.match(ticker))


def deduplicate(stocks: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for s in stocks:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate stocks.json for frontend search")
    parser.add_argument(
        "--source",
        choices=["edgar", "nasdaq", "sp500", "all"],
        default="all",
        help="Data source to use (default: all, merges edgar + nasdaq)",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Output path (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    stocks: list[dict] = []

    if args.source in ("edgar", "all"):
        try:
            stocks += fetch_from_edgar()
        except Exception as e:
            print(f"SEC EDGAR fetch failed: {e}")

    if args.source in ("nasdaq", "all"):
        try:
            stocks += fetch_from_nasdaq_ftp()
        except Exception as e:
            print(f"NASDAQ FTP fetch failed: {e}")

    if args.source == "sp500" or (not stocks):
        stocks += fetch_sp500()

    if not stocks:
        print("ERROR: No stocks fetched from any source.", file=sys.stderr)
        sys.exit(1)

    stocks = deduplicate(stocks)
    stocks.sort(key=lambda x: x["ticker"])

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    print(f"\n✅ Written {len(stocks)} stocks to {output_path}")


if __name__ == "__main__":
    main()

# Made with Bob

#!/usr/bin/env python3
"""
Fetch S&P 500 constituents and merge into stocks.json (no duplicates).
Run from repo root: python frontend/scripts/merge_sp500.py
"""
import csv
import json
import urllib.request
from pathlib import Path

# Paths (script is at frontend/scripts/merge_sp500.py)
REPO_ROOT = Path(__file__).resolve().parents[2]
STOCKS_JSON = REPO_ROOT / "frontend" / "public" / "stocks.json"
SP500_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"


def normalize_ticker(ticker: str) -> str:
    """Yahoo uses hyphen for class shares: BRK.B -> BRK-B, BF.B -> BF-B."""
    if not ticker or "." not in ticker:
        return ticker.strip().upper()
    return ticker.strip().upper().replace(".", "-")


def fetch_sp500():
    """Fetch and parse S&P 500 constituents CSV."""
    with urllib.request.urlopen(SP500_CSV_URL, timeout=15) as resp:
        text = resp.read().decode("utf-8")
    reader = csv.DictReader(text.splitlines())
    rows = []
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        security = (row.get("Security") or "").strip()
        if symbol and security:
            rows.append({"ticker": normalize_ticker(symbol), "name": security})
    return rows


def main():
    print("Fetching S&P 500 list...")
    sp500 = fetch_sp500()
    print(f"  Got {len(sp500)} constituents")

    print("Loading current stocks.json...")
    data = json.loads(STOCKS_JSON.read_text())
    existing_tickers = {e["ticker"] for e in data}
    for e in data:
        existing_tickers.add(normalize_ticker(e["ticker"]))

    added = []
    skipped_existing = 0

    print("Merging (add if not already present)...")
    for entry in sp500:
        ticker = entry["ticker"]
        if ticker in existing_tickers:
            skipped_existing += 1
            continue
        data.append(entry)
        existing_tickers.add(ticker)
        added.append(ticker)

    # One line per stock
    lines = ["["]
    for i, item in enumerate(data):
        line = "  " + json.dumps(item)
        if i < len(data) - 1:
            line += ","
        lines.append(line)
    lines.append("]")

    STOCKS_JSON.write_text("\n".join(lines) + "\n")
    print(f"Done. Added {len(added)} S&P 500 tickers. Already present: {skipped_existing}.")
    print(f"Total entries: {len(data)}")


if __name__ == "__main__":
    main()

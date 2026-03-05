#!/usr/bin/env python3
"""
Generate a consolidated stocks.json for frontend search.

Sources (in order of preference):
  1. SEC EDGAR company tickers JSON         -- free, no key, ~13k US-listed companies
  2. Curated S&P 500 and NASDAQ-100 lists  -- loaded from scripts/data/stock_lists.json
  3. Top crypto tickers                     -- loaded from scripts/data/stock_lists.json

The script writes frontend/public/stocks.json with entries:
  - Non-major tickers: {"ticker": "...", "name": "..."}
  - Major tickers:     {"ticker": "...", "name": "...", "sector": "...", "industry": "..."}

Major ticker sector/industry data is loaded from:
  backend/data/major_stocks_sectors.json
and missing entries are fetched from yfinance (if installed), then cached back.

Usage:
  python scripts/generate_stocks_json.py
  python scripts/generate_stocks_json.py --source edgar
  python scripts/generate_stocks_json.py --source sp500
  python scripts/generate_stocks_json.py --skip-major-sector-enrichment
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "frontend" / "public" / "stocks.json"
MAJOR_SECTORS_CACHE_PATH = (
    Path(__file__).parent.parent / "backend" / "data" / "major_stocks_sectors.json"
)
STOCK_LISTS_PATH = Path(__file__).parent / "data" / "stock_lists.json"


def _read_string_list(data: dict, key: str) -> list[str]:
    raw = data.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"stock lists config key '{key}' must be a list")
    values: list[str] = []
    for item in raw:
        val = str(item or "").strip().upper()
        if val:
            values.append(val)
    return values


def _read_crypto_list(data: dict) -> list[dict]:
    raw = data.get("crypto")
    if not isinstance(raw, list):
        raise ValueError("stock lists config key 'crypto' must be a list")
    values: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if ticker and name:
            values.append({"ticker": ticker, "name": name})
    return values


def _load_stock_lists(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Stock lists config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Stock lists config must be an object: {path}")
    return {
        "major_tickers": _read_string_list(data, "major_tickers"),
        "sp500": _read_string_list(data, "sp500"),
        "nasdaq100": _read_string_list(data, "nasdaq100"),
        "dow_jones": _read_string_list(data, "dow_jones"),
        "crypto": _read_crypto_list(data),
    }


_STOCK_LISTS = _load_stock_lists(STOCK_LISTS_PATH)
MAJOR_TICKERS = _STOCK_LISTS["major_tickers"]
SP500 = _STOCK_LISTS["sp500"]
NASDAQ100 = _STOCK_LISTS["nasdaq100"]
DOW_JONES = _STOCK_LISTS["dow_jones"]
CRYPTO_LIST = _STOCK_LISTS["crypto"]

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
# Source 2: Curated index lists (local, no network)
# ---------------------------------------------------------------------------

def _stocks_from_tickers(tickers: list[str], source_name: str) -> list[dict]:
    stocks: list[dict] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        stocks.append({"ticker": ticker, "name": ticker})
    stocks.sort(key=lambda x: x["ticker"])
    print(f"  → {len(stocks)} tickers from {source_name}")
    return stocks


def fetch_nasdaq100() -> list[dict]:
    """Return NASDAQ-100 tickers from the local curated list."""
    return _stocks_from_tickers(NASDAQ100, "local NASDAQ100 list")


def fetch_sp500() -> list[dict]:
    """Return S&P 500 tickers from the local curated list."""
    return _stocks_from_tickers(SP500, "local SP500 list")


# ---------------------------------------------------------------------------
# Source 3: Cryptocurrencies (top cryptos from config)
# ---------------------------------------------------------------------------

def fetch_crypto() -> list[dict]:
    """
    Fetch top cryptocurrencies that are tradeable via Yahoo Finance.
    Returns list of {"ticker": ..., "name": ...} dicts.
    """
    stocks = [{"ticker": item["ticker"], "name": item["name"]} for item in CRYPTO_LIST]
    print(f"  → {len(stocks)} cryptocurrencies added")
    return stocks


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


def load_existing_stocks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: could not read existing stocks file {path}: {e}")
        return []

    if not isinstance(data, list):
        return []

    stocks: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        name = str(item.get("name", "")).strip()
        if ticker and name:
            stock = {"ticker": ticker, "name": name}
            if item.get("sector"):
                stock["sector"] = item["sector"]
            if item.get("industry"):
                stock["industry"] = item["industry"]
            stocks.append(stock)
    return stocks


def _normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def _merge_major_ticker_lists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for tickers in lists:
        for ticker in tickers:
            norm = _normalize_ticker(ticker)
            if norm in seen:
                continue
            seen.add(norm)
            merged.append(norm)
    return merged


MERGED_MAJOR_TICKERS = _merge_major_ticker_lists(
    MAJOR_TICKERS,
    SP500,
    NASDAQ100,
    DOW_JONES,
)
_MAJOR_TICKER_SET = set(MERGED_MAJOR_TICKERS)


def load_major_sector_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: could not read major sectors cache {path}: {e}")
        return {}

    if not isinstance(data, dict):
        print(f"Warning: expected object in major sectors cache, got {type(data).__name__}")
        return {}

    cleaned: dict[str, dict] = {}
    for key, info in data.items():
        if not isinstance(info, dict):
            continue
        ticker = str(info.get("ticker") or key).upper()
        cleaned[ticker] = {
            "ticker": ticker,
            "name": info.get("name") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("market_cap"),
            "quote_type": info.get("quote_type"),
        }
    return cleaned


def save_major_sector_cache(cache: dict[str, dict], path: Path) -> None:
    payload = {}
    for ticker in sorted(cache):
        info = cache[ticker]
        payload[ticker] = {
            "ticker": ticker,
            "name": info.get("name") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("market_cap"),
            "quote_type": info.get("quote_type"),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_major_sector_data(tickers: list[str], delay: float) -> dict[str, dict]:
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        print("Warning: yfinance not installed, skipping major sector enrichment fetch.")
        return {}

    total = len(tickers)
    print(f"Fetching sector/industry for {total} major tickers via yfinance...")
    fetched: dict[str, dict] = {}

    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i}/{total}] {ticker}")
        try:
            info = yf.Ticker(ticker).info
            fetched[ticker] = {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "quote_type": info.get("quoteType"),
            }
        except Exception as e:
            print(f"    Warning: failed to fetch {ticker}: {e}")

        if i < total and delay > 0:
            time.sleep(max(0.0, delay + random.uniform(-0.1, 0.1)))

    return fetched


def _build_sector_index_by_normalized_ticker(sector_cache: dict[str, dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for ticker, info in sector_cache.items():
        index[_normalize_ticker(ticker)] = info
    return index


def collect_missing_major_tickers(stocks: list[dict], sector_cache: dict[str, dict]) -> list[str]:
    sector_index = _build_sector_index_by_normalized_ticker(sector_cache)
    seen_norm = set()
    missing = []

    for stock in stocks:
        ticker = stock["ticker"].upper()
        norm = _normalize_ticker(ticker)
        if norm not in _MAJOR_TICKER_SET or norm in seen_norm:
            continue
        seen_norm.add(norm)
        if norm not in sector_index:
            missing.append(ticker)
    return missing


def enrich_major_stocks(stocks: list[dict], sector_cache: dict[str, dict]) -> int:
    sector_index = _build_sector_index_by_normalized_ticker(sector_cache)
    enriched = 0

    for stock in stocks:
        norm = _normalize_ticker(stock["ticker"])
        if norm not in _MAJOR_TICKER_SET:
            continue

        info = sector_index.get(norm)
        if not info:
            continue

        sector = info.get("sector")
        industry = info.get("industry")
        if sector:
            stock["sector"] = sector
        if industry:
            stock["industry"] = industry
        if sector or industry:
            enriched += 1

    return enriched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate stocks.json for frontend search")
    parser.add_argument(
        "--source",
        choices=["edgar", "nasdaq", "crypto", "sp500", "all"],
        default="all",
        help="Data source to use (default: all, merges edgar + local index lists + crypto)",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Output path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--major-sectors-cache",
        default=str(MAJOR_SECTORS_CACHE_PATH),
        help=f"Major sector cache path (default: {MAJOR_SECTORS_CACHE_PATH})",
    )
    parser.add_argument(
        "--major-sectors-delay",
        type=float,
        default=0.5,
        help="Delay between yfinance major-sector requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--refresh-major-sectors",
        action="store_true",
        help="Ignore local major-sector cache and refetch from yfinance.",
    )
    parser.add_argument(
        "--skip-major-sector-enrichment",
        action="store_true",
        help="Do not enrich major tickers with sector/industry data.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    equity_stocks: list[dict] = []
    crypto_stocks: list[dict] = []

    if args.source in ("edgar", "all"):
        try:
            equity_stocks += fetch_from_edgar()
        except Exception as e:
            print(f"SEC EDGAR fetch failed: {e}")

    if args.source in ("nasdaq", "all"):
        try:
            equity_stocks += fetch_nasdaq100()
        except Exception as e:
            print(f"NASDAQ100 list load failed: {e}")

    if args.source in ("sp500", "all"):
        try:
            equity_stocks += fetch_sp500()
        except Exception as e:
            print(f"S&P 500 list load failed: {e}")

    if args.source == "all":
        existing_stocks = load_existing_stocks(output_path)
        if existing_stocks:
            print(f"Merging existing {output_path} ({len(existing_stocks)} entries) as fallback/supplement")
            equity_stocks += existing_stocks

    if args.source in ("crypto", "all"):
        try:
            crypto_stocks += fetch_crypto()
        except Exception as e:
            print(f"Crypto fetch failed: {e}")

    stocks = equity_stocks + crypto_stocks

    if not stocks:
        print("ERROR: No stocks fetched from any source.", file=sys.stderr)
        sys.exit(1)

    stocks = deduplicate(stocks)
    stocks.sort(key=lambda x: x["ticker"])

    if not args.skip_major_sector_enrichment:
        cache_path = Path(args.major_sectors_cache)
        sector_cache: dict[str, dict] = {}

        if not args.refresh_major_sectors:
            sector_cache = load_major_sector_cache(cache_path)
            if sector_cache:
                print(f"Loaded {len(sector_cache)} cached major sector records from {cache_path}")

        missing_major_tickers = collect_missing_major_tickers(stocks, sector_cache)
        if missing_major_tickers:
            fetched = fetch_major_sector_data(
                missing_major_tickers,
                delay=args.major_sectors_delay,
            )
            if fetched:
                sector_cache.update(fetched)
                save_major_sector_cache(sector_cache, cache_path)
                print(f"Updated major sectors cache: {cache_path}")

        enriched_count = enrich_major_stocks(stocks, sector_cache)
        print(f"  -> Enriched {enriched_count} major stocks with sector/industry")
    else:
        print("Skipped major sector/industry enrichment.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    print(f"\n✅ Written {len(stocks)} stocks to {output_path}")


if __name__ == "__main__":
    main()

# Made with Bob

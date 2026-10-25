#!/usr/bin/env python3
"""
Update S&P 500 and NASDAQ-100 lists from Wikipedia using pandas.

Requirements:
    pip install pandas lxml html5lib

Usage:
    python scripts/update_stock_lists.py
    python scripts/update_stock_lists.py --dry-run
"""

import argparse
import json
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

STOCK_LISTS_PATH = Path(__file__).parent / "data" / "stock_lists.json"

# Wikipedia URLs
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

MIN_SP500_COUNT = 450
MIN_NASDAQ100_COUNT = 90
MAX_REMOVAL_RATIO = 0.15


def extract_sp500_tickers() -> list[str]:
    """
    Extract S&P 500 tickers from Wikipedia using pandas.
    """
    if pd is None:
        print("Error: pandas is required. Install with: pip install pandas lxml html5lib")
        return []

    print(f"Fetching {SP500_URL}...")
    try:
        # Read all tables from the page with proper headers
        tables = pd.read_html(
            SP500_URL,
            storage_options={'User-Agent': 'Mozilla/5.0 (compatible; flowdeck/1.0)'}
        )
        
        # The first table contains the constituents
        df = tables[0]
        
        # The ticker column is usually named 'Symbol' or 'Ticker'
        ticker_col = None
        for col in df.columns:
            if 'symbol' in str(col).lower() or 'ticker' in str(col).lower():
                ticker_col = col
                break
        
        if ticker_col is None:
            # Try first column
            ticker_col = df.columns[0]
        
        # Extract tickers and normalize
        tickers = df[ticker_col].astype(str).str.strip().str.upper()
        tickers = tickers.str.replace('.', '-', regex=False)
        
        # Filter valid tickers
        tickers = [t for t in tickers if t and len(t) <= 6 and t != 'NAN']
        
        return sorted(list(set(tickers)))
    
    except Exception as e:
        print(f"Error fetching S&P 500: {e}")
        return []


def extract_nasdaq100_tickers() -> list[str]:
    """
    Extract NASDAQ-100 tickers from Wikipedia using pandas.
    """
    if pd is None:
        print("Error: pandas is required. Install with: pip install pandas lxml html5lib")
        return []

    print(f"Fetching {NASDAQ100_URL}...")
    try:
        # Read all tables from the page with proper headers
        tables = pd.read_html(
            NASDAQ100_URL,
            storage_options={'User-Agent': 'Mozilla/5.0 (compatible; flowdeck/1.0)'}
        )
        
        # Find the table with components (usually has 'Ticker' or 'Symbol' column)
        df = None
        for table in tables:
            for col in table.columns:
                if 'ticker' in str(col).lower() or 'symbol' in str(col).lower():
                    df = table
                    break
            if df is not None:
                break
        
        if df is None:
            print("Warning: Could not find NASDAQ-100 components table")
            return []
        
        # Find ticker column
        ticker_col = None
        for col in df.columns:
            if 'ticker' in str(col).lower() or 'symbol' in str(col).lower():
                ticker_col = col
                break
        
        if ticker_col is None:
            ticker_col = df.columns[0]
        
        # Extract tickers and normalize
        tickers = df[ticker_col].astype(str).str.strip().str.upper()
        tickers = tickers.str.replace('.', '-', regex=False)
        
        # Filter valid tickers
        tickers = [t for t in tickers if t and len(t) <= 6 and t != 'NAN']
        
        return sorted(list(set(tickers)))
    
    except Exception as e:
        print(f"Error fetching NASDAQ-100: {e}")
        return []


def load_stock_lists(path: Path) -> dict:
    """Load existing stock lists."""
    if not path.exists():
        raise FileNotFoundError(f"Stock lists file not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_stock_lists(path: Path, data: dict) -> None:
    """Save stock lists to file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')  # Add trailing newline


def validate_ticker_update(
    index_name: str,
    new_tickers: list[str],
    old_tickers: list[str],
    min_count: int,
) -> list[str]:
    """Return safety errors for implausible index updates."""
    errors = []
    if len(new_tickers) < min_count:
        errors.append(
            f"{index_name} parse returned {len(new_tickers)} tickers; expected at least {min_count}"
        )

    if old_tickers:
        removed = set(old_tickers) - set(new_tickers)
        max_removed = max(10, int(len(old_tickers) * MAX_REMOVAL_RATIO))
        if len(removed) > max_removed:
            errors.append(
                f"{index_name} update would remove {len(removed)} tickers; safety limit is {max_removed}"
            )

    return errors


def safe_ticker_update(
    index_name: str,
    fetched_tickers: list[str],
    old_tickers: list[str],
    min_count: int,
    force: bool = False,
) -> list[str]:
    """Use fetched tickers only when they pass sanity checks, unless forced."""
    if not fetched_tickers:
        print(f"✗ Failed to fetch {index_name}, keeping existing list")
        return old_tickers

    print(f"✓ Fetched {index_name}: {len(fetched_tickers)} stocks")
    validation_errors = validate_ticker_update(index_name, fetched_tickers, old_tickers, min_count)
    if validation_errors and not force:
        for error in validation_errors:
            print(f"✗ {error}")
        print(f"✗ Refusing to update {index_name}; keeping existing list (use --force to override)")
        return old_tickers

    if validation_errors and force:
        for error in validation_errors:
            print(f"! {error} (--force set, accepting update)")

    return fetched_tickers


def main():
    parser = argparse.ArgumentParser(description='Update S&P 500 and NASDAQ-100 lists')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without saving')
    parser.add_argument('--force', action='store_true', help='Save even when safety checks reject a fetched list')
    args = parser.parse_args()
    
    # Load existing lists
    print(f"Loading existing lists from {STOCK_LISTS_PATH}")
    stock_lists = load_stock_lists(STOCK_LISTS_PATH)
    
    old_sp500 = stock_lists.get('sp500', [])
    old_nasdaq100 = stock_lists.get('nasdaq100', [])
    
    print(f"Current S&P 500: {len(old_sp500)} stocks")
    print(f"Current NASDAQ-100: {len(old_nasdaq100)} stocks")
    print()
    
    # Fetch new lists
    new_sp500 = safe_ticker_update(
        "S&P 500",
        extract_sp500_tickers(),
        old_sp500,
        MIN_SP500_COUNT,
        force=args.force,
    )
    
    new_nasdaq100 = safe_ticker_update(
        "NASDAQ-100",
        extract_nasdaq100_tickers(),
        old_nasdaq100,
        MIN_NASDAQ100_COUNT,
        force=args.force,
    )
    
    print()
    
    # Show changes
    sp500_added = set(new_sp500) - set(old_sp500)
    sp500_removed = set(old_sp500) - set(new_sp500)
    nasdaq100_added = set(new_nasdaq100) - set(old_nasdaq100)
    nasdaq100_removed = set(old_nasdaq100) - set(new_nasdaq100)
    
    print("Changes:")
    print(f"  S&P 500:")
    print(f"    Added: {len(sp500_added)} stocks {sorted(sp500_added) if sp500_added else ''}")
    print(f"    Removed: {len(sp500_removed)} stocks {sorted(sp500_removed) if sp500_removed else ''}")
    print(f"  NASDAQ-100:")
    print(f"    Added: {len(nasdaq100_added)} stocks {sorted(nasdaq100_added) if nasdaq100_added else ''}")
    print(f"    Removed: {len(nasdaq100_removed)} stocks {sorted(nasdaq100_removed) if nasdaq100_removed else ''}")
    print()
    
    if args.dry_run:
        print("Dry run - no changes saved")
        return
    
    # Update lists
    stock_lists['sp500'] = new_sp500
    stock_lists['nasdaq100'] = new_nasdaq100
    
    # Save
    save_stock_lists(STOCK_LISTS_PATH, stock_lists)
    print(f"✅ Updated {STOCK_LISTS_PATH}")
    print()
    print("Next steps:")
    print("  1. Review the changes above")
    print("  2. Run: python scripts/generate_stocks_json.py")
    print("  3. This will regenerate backend/data/major_stocks_sectors.json")


if __name__ == '__main__':
    main()

# Made with Bob

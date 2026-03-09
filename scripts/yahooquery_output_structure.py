#!/usr/bin/env python3
"""
Print actual yahooquery output payloads for a ticker.

Example:
  python scripts/yahooquery_output_structure.py --ticker AAPL
  python scripts/yahooquery_output_structure.py --ticker MSFT --sections financial_data,recommendation_trend
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable, Dict, Iterable

try:
    from yahooquery import Ticker
except Exception:
    print("Missing dependency: yahooquery. Install with: pip install yahooquery")
    sys.exit(1)


def to_plain(obj: Any) -> Any:
    """Convert pandas/yahooquery objects into plain Python containers."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]

    if hasattr(obj, "to_dict"):
        # DataFrame first
        try:
            return to_plain(obj.to_dict(orient="records"))
        except Exception:
            pass
        # Series / generic
        try:
            return to_plain(obj.to_dict())
        except Exception:
            pass

    return str(obj)


def extract_symbol_payload(data: Any, symbol: str) -> Any:
    """Return symbol-specific payload when yahooquery returns a dict keyed by symbol."""
    if not isinstance(data, dict):
        return data

    upper = symbol.upper()
    if upper in data:
        return data[upper]

    for key, value in data.items():
        if str(key).upper() == upper:
            return value
    return data


def section_fetchers() -> Dict[str, Callable[[Ticker], Any]]:
    return {
        "price": lambda t: t.price,
        "summary_detail": lambda t: t.summary_detail,
        "financial_data": lambda t: t.financial_data,
        "recommendation_trend": lambda t: t.recommendation_trend,
        "asset_profile": lambda t: t.asset_profile,
    }


def parse_sections(raw: str, valid: Iterable[str]) -> list[str]:
    names = [s.strip() for s in raw.split(",") if s.strip()]
    if not names:
        return list(valid)
    invalid = [n for n in names if n not in valid]
    if invalid:
        raise ValueError(f"Unknown section(s): {', '.join(invalid)}")
    return names


def main() -> int:
    fetchers = section_fetchers()

    parser = argparse.ArgumentParser(description="Inspect yahooquery output payloads")
    parser.add_argument("--ticker", default="AAPL", help="Ticker symbol (default: AAPL)")
    parser.add_argument(
        "--sections",
        default="price,summary_detail,financial_data,recommendation_trend,asset_profile",
        help=f"Comma-separated sections. Options: {', '.join(fetchers.keys())}",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON indent for actual output (default: 2)")
    args = parser.parse_args()

    ticker = args.ticker.upper()
    try:
        selected = parse_sections(args.sections, fetchers.keys())
    except ValueError as exc:
        print(str(exc))
        return 2

    print(f"Ticker: {ticker}")
    print(f"Sections: {', '.join(selected)}")
    print("=" * 80)

    try:
        client = Ticker(ticker)
    except Exception as exc:
        print(f"Failed to initialize yahooquery client: {exc}")
        print("Check internet/DNS access, then run again.")
        return 1

    for name in selected:
        print(f"\n[{name}]")
        try:
            raw = fetchers[name](client)
            plain = to_plain(raw)
            payload = extract_symbol_payload(plain, ticker)
            print("Actual payload:")
            print(json.dumps(payload, indent=max(0, args.indent), ensure_ascii=True, default=str))
        except Exception as exc:
            print(f"Error: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""
Manually inspect the deterministic event layer for a ticker.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add the backend dir to path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

# Load environment variables
env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from backend.processing import get_ticker_event_summary
from data_layer import get_data_gateway, init_data_gateway
from data_layer.market import MarketDataLayer
from database import init_db
from services.edgar_service import get_edgar_service
from services.report_service import ReportService


def calculate_ticker_events(ticker):
    """Calculate event layer for a given ticker."""
    as_of_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"Calculating event layer for {ticker} as of {as_of_date}\n")

    # Initialize database and data gateway
    try:
        init_db()
        print("  ✓ Database initialized")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

    # Initialize data gateway if not already done
    try:
        gateway = get_data_gateway()
        print("  ✓ Data gateway already initialized")
    except Exception:
        print("Initializing data gateway...")
        try:
            init_data_gateway(
                market=MarketDataLayer(),
                reports=ReportService(),
                edgar=get_edgar_service(),
            )
            gateway = get_data_gateway()
            print("  ✓ Data gateway initialized")
        except Exception as e2:
            print(f"Error initializing data gateway: {e2}")
            import traceback

            traceback.print_exc()
            return None

    print("Fetching cached ticker event snapshot...")
    try:
        event_summary = get_ticker_event_summary(
            gateway,
            ticker,
            as_of_date=as_of_date,
        )
        print("  ✓ Event calculation complete\n")

        print(f"Event Layer Summary for {ticker}:")
        print(f"  Event Score: {event_summary.event_score}")
        print(f"  Event Count: {event_summary.event_count}")
        print(f"  Dominant Events: {event_summary.dominant_events}")
        print("\nDetected Events:")
        for event in event_summary.events:
            print(f"  - {event.event_type} ({event.domain})")
            print(f"    Strength: {event.strength}")
            print(f"    Detected On: {event.detected_on}")
            if event.metric_value is not None:
                print(f"    Metric Value: {event.metric_value}")
            print()

        return event_summary
    except Exception as e:
        print(f"Error calculating events: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/tests/manual_event_inspector.py <TICKER>")
        print("Example: python backend/tests/manual_event_inspector.py IBM")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    result = calculate_ticker_events(ticker)
    if result:
        print("✓ Event layer calculation successful")
    else:
        print("✗ Event layer calculation failed")
        sys.exit(1)

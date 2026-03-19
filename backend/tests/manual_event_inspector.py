#!/usr/bin/env python
"""
Manually inspect the deterministic event layer for a ticker.
"""

import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Add the backend dir to path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

# Load environment variables
env_path = Path(__file__).resolve().parents[2] / "backend" / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from backend.processing import extract_ticker_events, parse_rsi_indicator_data
from data_layer import get_data_gateway, init_data_gateway
from data_layer.market import MarketDataLayer
from data_layer.sources.edgar import EdgarDataSource
from data_layer.sources.market import CachedMarketSource
from data_layer.sources.reports import ReportDataSource
from data_layer.sources.user import UserPortfolioSource
from database import init_db
from services.edgar_service import get_edgar_service
from services.report_service import ReportService


def calculate_ticker_events(ticker):
    """Calculate event layer for a given ticker."""
    as_of_date = datetime.utcnow().strftime("%Y-%m-%d")

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
            market_layer = MarketDataLayer()
            market_source = CachedMarketSource(market_layer)
            report_source = ReportDataSource(ReportService())
            user_source = UserPortfolioSource()
            edgar_source = EdgarDataSource(get_edgar_service())
            init_data_gateway(
                market=market_source,
                reports=report_source,
                user=user_source,
                edgar=edgar_source,
            )
            gateway = get_data_gateway()
            print("  ✓ Data gateway initialized")
        except Exception as e2:
            print(f"Error initializing data gateway: {e2}")
            import traceback

            traceback.print_exc()
            return None

    # Fetch historical data (1 year)
    print("Fetching historical price data...")
    try:
        hist_data = gateway.get_historical(ticker, period="1y", interval="1d")
        if hist_data.get("error"):
            print(f"Error fetching historical data: {hist_data.get('error')}")
            return None
        bars = hist_data.get("data", [])
        if not bars:
            print("No historical data available")
            return None
        print(f"  ✓ Fetched {len(bars)} daily bars")
    except Exception as e:
        print(f"Error fetching historical data: {e}")
        import traceback

        traceback.print_exc()
        return None

    # Fetch future events (earnings, etc.)
    print("Fetching future events...")
    try:
        events_data = gateway.get_future_events(ticker)
        if events_data.get("error"):
            print(f"Warning: Could not fetch future events: {events_data.get('error')}")
            future_events = None
        else:
            future_events = events_data
            events_list = future_events.get("events", []) if isinstance(future_events, dict) else []
            print(f"  ✓ Fetched {len(events_list)} future events")
    except Exception as e:
        print(f"Warning: Could not fetch future events: {e}")
        future_events = None

    print("Fetching insider transactions...")
    try:
        insider_transactions = gateway.get_insider_transactions(ticker, limit=50)
        txs = insider_transactions.get("transactions", []) if isinstance(insider_transactions, dict) else []
        print(f"  ✓ Fetched {len(txs)} insider transactions")
    except Exception as e:
        print(f"Warning: Could not fetch insider transactions: {e}")
        insider_transactions = None

    print("Fetching RSI data...")
    try:
        raw_rsi = gateway.get_indicators(ticker, "rsi", as_of_date, 60)
        rsi_data = parse_rsi_indicator_data(raw_rsi)
        print(f"  ✓ Parsed {len(rsi_data)} RSI points")
    except Exception as e:
        print(f"Warning: Could not fetch RSI data: {e}")
        rsi_data = None

    # Calculate event layer
    print("\nCalculating events...")
    try:
        event_summary = extract_ticker_events(
            ticker,
            bars=bars,
            as_of_date=as_of_date,
            future_events=future_events,
            insider_transactions=insider_transactions,
            rsi_data=rsi_data,
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

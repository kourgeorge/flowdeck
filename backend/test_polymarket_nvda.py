#!/usr/bin/env python3
"""
Test script to diagnose Polymarket data extraction for NVDA.
This will help identify why the probabilities don't match between Polymarket and FlowDeck.
"""

import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from services.polymarket_service import get_polymarket_service

def main():
    """Test Polymarket data extraction for NVDA."""
    print("=" * 80)
    print("Testing Polymarket Data Extraction for NVDA")
    print("=" * 80)
    
    service = get_polymarket_service()
    
    # Test health check first
    print("\n1. Health Check")
    print("-" * 80)
    is_healthy = service.health_check()
    print(f"Polymarket API Status: {'✓ Healthy' if is_healthy else '✗ Unhealthy'}")
    
    if not is_healthy:
        print("ERROR: Polymarket API is not accessible. Exiting.")
        return
    
    # Get ticker sentiment
    print("\n2. Fetching NVDA Sentiment")
    print("-" * 80)
    result = service.get_ticker_sentiment(
        ticker="NVDA",
        company_info={"name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors"},
        max_markets=50,
        top_n=10
    )
    
    # Display results
    print("\n3. Results Summary")
    print("-" * 80)
    print(f"Ticker: {result['ticker']}")
    print(f"Overall Sentiment: {result['overall_sentiment']:.4f} ({result['overall_sentiment']*100:.2f}%)")
    print(f"Confidence: {result['confidence']:.4f} ({result['confidence']*100:.2f}%)")
    print(f"Trend: {result['trend']}")
    print(f"Market Count: {result['market_count']}")
    print(f"Last Updated: {result['last_updated']}")
    
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    # Display top markets
    print("\n4. Top Markets")
    print("-" * 80)
    for idx, market in enumerate(result['top_markets'], 1):
        print(f"\n{idx}. {market['question']}")
        print(f"   ID: {market['id']}")
        print(f"   Probability: {market['probability']:.4f} ({market['probability']*100:.2f}%)")
        print(f"   Volume: ${market['volume']:,}")
        print(f"   Liquidity: ${market['liquidity']:,}")
        print(f"   Relevance: {market.get('relevance_score', 0):.2f}")
        print(f"   Matched Keyword: {market.get('matched_keyword', 'N/A')}")
        print(f"   Narrative: {market.get('narrative', 'N/A')}")
        print(f"   URL: {market['url']}")
    
    # Display narratives
    if result['narratives']:
        print("\n5. Narrative Breakdown")
        print("-" * 80)
        for narrative, data in result['narratives'].items():
            print(f"\n{narrative}:")
            print(f"   Sentiment: {data['sentiment']:.4f} ({data['sentiment']*100:.2f}%)")
            print(f"   Confidence: {data['confidence']:.4f}")
            print(f"   Market Count: {data['market_count']}")
            print(f"   Trend: {data['trend']}")
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()

# Made with Bob

#!/usr/bin/env python3
"""
Test script for the Valuation Analyst component.
"""

import os
import sys
from datetime import date

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_engine.tradingagents.graph.trading_graph import TradingAgentsGraph


def test_valuation_analyst():
    """Test the valuation analyst with a simple ticker."""
    
    print("=" * 80)
    print("VALUATION ANALYST TEST")
    print("=" * 80)
    
    # Create graph with only valuation analyst for focused testing
    print("\n1. Creating TradingAgents graph with valuation analyst...")
    try:
        graph = TradingAgentsGraph(
            selected_analysts=["valuation"],
            debug=False,
            config={
                "info_service_url": os.getenv("INFO_SERVICE_URL", "http://localhost:8000"),
            }
        )
        print("✓ Graph created successfully")
    except Exception as e:
        print(f"✗ Failed to create graph: {e}")
        return False
    
    # Run analysis on a test ticker
    ticker = "AAPL"
    trade_date = "2024-01-15"
    
    print(f"\n2. Running valuation analysis for {ticker} on {trade_date}...")
    try:
        final_state, signal = graph.propagate(ticker, trade_date)
        print("✓ Analysis completed")
    except Exception as e:
        print(f"✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check results
    print("\n3. Checking valuation results...")
    
    valuation_report = final_state.get("valuation_report", "")
    valuation_score = final_state.get("valuation_score")
    fair_value_bear = final_state.get("fair_value_bear")
    fair_value_base = final_state.get("fair_value_base")
    fair_value_bull = final_state.get("fair_value_bull")
    current_discount_pct = final_state.get("current_discount_pct")
    valuation_conviction = final_state.get("valuation_conviction")
    key_assumptions = final_state.get("valuation_key_assumptions", [])
    key_takeaways = final_state.get("valuation_key_takeaways", [])
    
    print("\n" + "=" * 80)
    print("VALUATION RESULTS")
    print("=" * 80)
    
    if valuation_report:
        print(f"\n📊 Valuation Score: {valuation_score}/5")
        print(f"💰 Fair Value (Bear): ${fair_value_bear}")
        print(f"💰 Fair Value (Base): ${fair_value_base}")
        print(f"💰 Fair Value (Bull): ${fair_value_bull}")
        print(f"📈 Current Discount: {current_discount_pct}%")
        print(f"🎯 Conviction: {valuation_conviction}")
        
        if key_assumptions:
            print(f"\n🔑 Key Assumptions:")
            for i, assumption in enumerate(key_assumptions, 1):
                print(f"   {i}. {assumption}")
        
        if key_takeaways:
            print(f"\n💡 Key Takeaways:")
            for i, takeaway in enumerate(key_takeaways, 1):
                print(f"   {i}. {takeaway}")
        
        print(f"\n📄 Full Report:")
        print("-" * 80)
        print(valuation_report[:1000])  # Print first 1000 chars
        if len(valuation_report) > 1000:
            print(f"\n... (truncated, full report is {len(valuation_report)} characters)")
        
        print("\n" + "=" * 80)
        print("✓ TEST PASSED - Valuation analyst produced results")
        print("=" * 80)
        return True
    else:
        print("\n✗ TEST FAILED - No valuation report generated")
        print(f"Final state keys: {list(final_state.keys())}")
        return False


if __name__ == "__main__":
    success = test_valuation_analyst()
    sys.exit(0 if success else 1)

# Made with Bob

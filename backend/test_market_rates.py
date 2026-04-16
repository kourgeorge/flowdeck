#!/usr/bin/env python3
"""
Test script for market rates service.
Run from backend directory: python test_market_rates.py
"""

import sys
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv()

from services.market_rates_service import MarketRatesService

def test_market_rates():
    print("Testing Market Rates Service")
    print("=" * 50)
    
    # Test fetching market rates
    print("\n1. Fetching market rates from FRED...")
    rates = MarketRatesService.get_market_rates()
    
    print(f"\nRisk-Free Rate (10Y Treasury): {rates['risk_free_rate']:.4f} ({rates['risk_free_rate']*100:.2f}%)")
    print(f"Treasury 10Y: {rates['treasury_10y']:.4f} ({rates['treasury_10y']*100:.2f}%)")
    print(f"Treasury 2Y: {rates['treasury_2y']:.4f} ({rates['treasury_2y']*100:.2f}%)")
    print(f"Treasury 3M: {rates['treasury_3m']:.4f} ({rates['treasury_3m']*100:.2f}%)")
    print(f"Last Updated: {rates['last_updated']}")
    print(f"Source: {rates['source']}")
    print(f"Cache Age: {rates['cache_age_hours']} hours")
    
    # Test convenience method
    print("\n2. Testing convenience method...")
    rfr = MarketRatesService.get_risk_free_rate()
    print(f"Risk-Free Rate: {rfr:.4f} ({rfr*100:.2f}%)")
    
    # Test cache
    print("\n3. Testing cache (should be instant)...")
    rates2 = MarketRatesService.get_market_rates()
    print(f"Cache Age: {rates2['cache_age_hours']} hours")
    
    # Test force refresh
    print("\n4. Testing force refresh...")
    MarketRatesService.clear_cache()
    rates3 = MarketRatesService.get_market_rates(force_refresh=True)
    print(f"After refresh - Cache Age: {rates3['cache_age_hours']} hours")
    
    print("\n5. Testing VIX and Market Risk Premium...")
    vix = rates.get('vix')
    mrp = rates.get('market_risk_premium', 0.055)
    if vix:
        print(f"VIX: {vix:.2f}")
        print(f"Market Risk Premium: {mrp:.4f} ({mrp*100:.2f}%)")
        print(f"VIX Interpretation:")
        if vix < 15:
            print("  → Low volatility (below-average risk premium)")
        elif vix < 25:
            print("  → Normal volatility (standard risk premium)")
        elif vix < 35:
            print("  → Elevated volatility (above-average risk premium)")
        else:
            print("  → High stress (maximum risk premium)")
    else:
        print("VIX: Not available")
        print(f"Market Risk Premium: {mrp:.4f} ({mrp*100:.2f}%) [fallback]")
    
    print("\n6. Testing manual VIX scenarios...")
    test_scenarios = [
        (12.0, "Low volatility"),
        (18.0, "Normal"),
        (30.0, "Elevated"),
        (45.0, "High stress")
    ]
    for test_vix, description in test_scenarios:
        test_mrp = MarketRatesService.calculate_market_risk_premium(test_vix)
        print(f"  VIX {test_vix:5.1f} ({description:15s}): {test_mrp:.4f} ({test_mrp*100:.2f}%)")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    
    return rates

if __name__ == "__main__":
    try:
        rates = test_market_rates()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob

#!/usr/bin/env python3
"""
Test script for dynamic terminal growth calculation.
Tests different sectors and growth stages to verify correct terminal growth rates.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_engine.tradingagents.agents.utils.valuation_tools import _calculate_terminal_growth


def test_terminal_growth():
    """Test terminal growth calculation for various scenarios."""
    
    print("=" * 80)
    print("TERMINAL GROWTH CALCULATION TEST")
    print("=" * 80)
    print()
    
    # Test cases: (sector, is_high_growth, revenue_growth, description)
    test_cases = [
        # Mature companies in different sectors
        ("Utilities", False, 0.03, "Mature Utility (e.g., Duke Energy)"),
        ("Consumer Staples", False, 0.05, "Mature Consumer Staples (e.g., Procter & Gamble)"),
        ("Technology", False, 0.08, "Mature Tech (e.g., Apple)"),
        ("Healthcare", False, 0.06, "Mature Healthcare (e.g., Johnson & Johnson)"),
        ("Financials", False, 0.04, "Mature Financial (e.g., JPMorgan)"),
        
        # High-growth companies
        ("Technology", True, 0.35, "High-Growth Tech (e.g., Nvidia)"),
        ("Technology", True, 0.15, "Moderate-Growth Tech (15% growth)"),
        ("Consumer Discretionary", True, 0.30, "High-Growth Consumer (e.g., Tesla)"),
        ("Healthcare", True, 0.25, "High-Growth Healthcare (e.g., Biotech)"),
        ("Communication Services", True, 0.28, "High-Growth Comm (e.g., Meta)"),
        
        # Edge cases
        (None, False, 0.05, "Unknown Sector (Mature)"),
        (None, True, 0.25, "Unknown Sector (High-Growth)"),
        ("Energy", False, 0.04, "Mature Energy (e.g., ExxonMobil)"),
        ("Real Estate", False, 0.03, "Mature REIT"),
    ]
    
    print(f"{'Description':<45} {'Sector':<25} {'Growth':<8} {'Bear':<8} {'Base':<8} {'Bull':<8}")
    print("-" * 110)
    
    for sector, is_high_growth, revenue_growth, description in test_cases:
        result = _calculate_terminal_growth(
            sector=sector,
            is_high_growth=is_high_growth,
            revenue_growth=revenue_growth
        )
        
        growth_stage = "High" if is_high_growth else "Mature"
        sector_display = sector or "Unknown"
        
        print(f"{description:<45} {sector_display:<25} {growth_stage:<8} "
              f"{result['bear']*100:>6.2f}% {result['base']*100:>6.2f}% {result['bull']*100:>6.2f}%")
    
    print()
    print("=" * 80)
    print("KEY OBSERVATIONS")
    print("=" * 80)
    print()
    print("1. Sector Impact:")
    print("   - Utilities: Lowest (2.0% base) - Regulated, mature")
    print("   - Technology: Highest (3.5% base) - Innovation-driven")
    print("   - Healthcare: Mid-high (3.0% base) - Demographics")
    print()
    print("2. Growth Stage Impact:")
    print("   - High-growth companies (>20% revenue growth) get +0.5% premium")
    print("   - This reflects market leaders sustaining above-average growth")
    print()
    print("3. Bounds:")
    print("   - Minimum terminal growth: 1.5% (bear case)")
    print("   - Maximum terminal growth: 4.5% (bull case)")
    print("   - Base terminal growth capped at 4.0%")
    print()
    print("4. Comparison to Old Hardcoded Values:")
    print("   - Old: Bear=2.0%, Base=3.0%, Bull=4.0% (ALL companies)")
    print("   - New: Dynamic based on sector and growth stage")
    print("   - Impact: More accurate valuations, especially for utilities and tech")
    print()
    
    # Calculate impact example
    print("=" * 80)
    print("VALUATION IMPACT EXAMPLE")
    print("=" * 80)
    print()
    print("Assume $1B terminal FCF, 10% WACC:")
    print()
    
    scenarios = [
        ("Mature Utility", 0.020, "Old: 3.0%", 0.030),
        ("High-Growth Tech", 0.040, "Old: 3.0%", 0.030),
    ]
    
    terminal_fcf = 1_000_000_000  # $1B
    wacc = 0.10
    
    for description, new_rate, old_label, old_rate in scenarios:
        new_terminal_value = terminal_fcf * (1 + new_rate) / (wacc - new_rate)
        old_terminal_value = terminal_fcf * (1 + old_rate) / (wacc - old_rate)
        difference = new_terminal_value - old_terminal_value
        pct_diff = (difference / old_terminal_value) * 100
        
        print(f"{description}:")
        print(f"  New terminal growth: {new_rate*100:.1f}% → Terminal Value: ${new_terminal_value/1e9:.2f}B")
        print(f"  {old_label} → Terminal Value: ${old_terminal_value/1e9:.2f}B")
        print(f"  Difference: ${difference/1e9:.2f}B ({pct_diff:+.1f}%)")
        print()
    
    print("This shows how sector-specific terminal growth significantly impacts valuations!")
    print()


if __name__ == "__main__":
    test_terminal_growth()

# Made with Bob

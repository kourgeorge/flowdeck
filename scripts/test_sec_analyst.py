#!/usr/bin/env python3
"""
Standalone script to test the SEC analyst independently.
This demonstrates how the SEC analyst works with file exploration tools.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import from ai_engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Try backend/.env first, then root .env
    backend_env = Path(__file__).parent.parent / 'backend' / '.env'
    root_env = Path(__file__).parent.parent / '.env'
    
    if backend_env.exists():
        load_dotenv(backend_env)
        print(f"✓ Loaded environment from {backend_env}\n")
    elif root_env.exists():
        load_dotenv(root_env)
        print(f"✓ Loaded environment from {root_env}\n")
    else:
        print(f"⚠️  No .env file found at {backend_env} or {root_env}")
        print("   Create one from .env.example and set OPENAI_API_KEY\n")
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv\n")

from ai_engine.llm_provider import get_config_from_env, get_llm
from ai_engine.tradingagents.agents.analysts.sec_analyst import create_sec_analyst


def run_sec_analyst_test(ticker: str = "AAPL"):
    """
    Run the SEC analyst independently on a given ticker.
    
    Args:
        ticker: Stock ticker symbol (default: AAPL)
    """
    print(f"\n{'='*80}")
    print(f"SEC ANALYST INDEPENDENT TEST")
    print(f"{'='*80}")
    print(f"Ticker: {ticker}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*80}\n")
    
    # Check for required environment variables
    info_service_url = os.getenv("INFO_SERVICE_URL")
    if not info_service_url:
        print("⚠️  WARNING: INFO_SERVICE_URL not set. SEC analyst requires backend service.")
        print("   Set it with: export INFO_SERVICE_URL=http://localhost:8000")
        print("   Make sure the backend is running.\n")
    else:
        print(f"✓ INFO_SERVICE_URL: {info_service_url}\n")
    
    # Get LLM configuration from environment
    print("Initializing LLM...")
    config = get_config_from_env()
    provider = config.get("llm_provider", "openai")
    model = config.get("quick_think_llm", "gpt-4o-mini")
    print(f"✓ Provider: {provider}")
    print(f"✓ Model: {model}\n")
    
    # Create LLM instance
    llm = get_llm("quick", config)
    
    # Create SEC analyst
    print("Creating SEC analyst...")
    sec_analyst = create_sec_analyst(llm)
    print("✓ SEC analyst created with tools:")
    print("  - get_sec_toc (see filing structure)")
    print("  - get_sec_stats (get overview)")
    print("  - grep_sec_filing (search content)")
    print("  - read_sec_section (read specific section)")
    print("  - read_sec_lines (read line ranges)")
    print("  - get_edgar_filing_content (fallback extraction)\n")
    
    # Create minimal state for the analyst
    state = {
        "company_of_interest": ticker,
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
    }
    
    print(f"Running SEC analyst for {ticker}...")
    print(f"{'='*80}\n")
    
    try:
        # Run the analyst
        result = sec_analyst(state)
        
        # Display results
        print(f"\n{'='*80}")
        print("SEC ANALYST RESULTS")
        print(f"{'='*80}\n")
        
        # Report
        if "sec_report" in result:
            print("📄 SEC REPORT:")
            print("-" * 80)
            print(result["sec_report"])
            print()
        
        # Score
        if "sec_score" in result:
            score = result["sec_score"]
            print(f"📊 SEC SCORE: {score}/10")
            if score:
                if score >= 8:
                    print("   ✓ Low regulatory concern, clean disclosures")
                elif score >= 5:
                    print("   ⚠️  Moderate regulatory concerns")
                else:
                    print("   ⚠️  Higher regulatory/filing risk or disclosure concerns")
            print()
        
        # Key Takeaways
        if "sec_key_takeaways" in result and result["sec_key_takeaways"]:
            print("🔑 KEY TAKEAWAYS:")
            for i, takeaway in enumerate(result["sec_key_takeaways"], 1):
                print(f"   {i}. {takeaway}")
            print()
        
        # Usage statistics
        if "report_usage" in result and "sec_report" in result["report_usage"]:
            usage = result["report_usage"]["sec_report"]
            print("📈 USAGE STATISTICS:")
            print(f"   Input tokens:  {usage.get('input_tokens', 0):,}")
            print(f"   Output tokens: {usage.get('output_tokens', 0):,}")
            print(f"   Total tokens:  {usage.get('total_tokens', 0):,}")
            print(f"   Cost (USD):    ${usage.get('cost_usd', 0):.4f}")
            print()
        
        # Resources used
        if "report_resources" in result and result["report_resources"]:
            print("🔧 TOOLS USED:")
            for i, resource in enumerate(result["report_resources"], 1):
                tool_name = resource.get("tool", "unknown")
                args = resource.get("args", {})
                print(f"   {i}. {tool_name}")
                for key, value in args.items():
                    print(f"      - {key}: {value}")
            print()
        
        print(f"{'='*80}")
        print("✓ SEC analyst completed successfully!")
        print(f"{'='*80}\n")
        
        return result
        
    except Exception as e:
        print(f"\n{'='*80}")
        print("❌ ERROR RUNNING SEC ANALYST")
        print(f"{'='*80}")
        print(f"Error: {str(e)}")
        print(f"\nFull traceback:")
        import traceback
        traceback.print_exc()
        print(f"{'='*80}\n")
        return None


if __name__ == "__main__":
    # Get ticker from command line or use default
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    
    # Run the test
    result = run_sec_analyst_test(ticker)
    
    # Exit with appropriate code
    sys.exit(0 if result else 1)

# Made with Bob

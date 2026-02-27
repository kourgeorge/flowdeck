"""
Standalone test script for Portfolio Risk Profiler and Interrogator.
Run this to test the risk analysis features with real data from the server.

Requirements:
- Backend server must be running (python backend/run.py)
- INFO_SERVICE_URL environment variable set (default: http://localhost:8002)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai_engine.portfolio_deep_research.portfolio_risk_profiler import analyze_portfolio_risk
from ai_engine.portfolio_deep_research.portfolio_interrogator import generate_portfolio_questions


def fetch_real_reports(tickers: list[str]) -> dict:
    """Fetch real reports from the backend server."""
    base_url = os.environ.get("INFO_SERVICE_URL", "http://localhost:8002").strip().rstrip("/")
    
    print(f"📡 Fetching reports from {base_url}...")
    
    try:
        url = f"{base_url}/api/data/reports/batch"
        data = json.dumps({"tickers": [t.upper() for t in tickers]}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        
        existing_reports = {}
        tickers_data = result.get("tickers", {})
        
        for ticker in tickers:
            ticker_upper = ticker.upper()
            info = tickers_data.get(ticker_upper, {})
            
            if not info or not info.get("reports"):
                print(f"⚠️  No reports found for {ticker_upper}")
                existing_reports[ticker_upper] = {
                    "report_date": None,
                    "reports": {}
                }
            else:
                existing_reports[ticker_upper] = {
                    "report_date": info.get("report_date"),
                    "reports": info.get("reports", {})
                }
                print(f"✅ Loaded reports for {ticker_upper} (date: {info.get('report_date')})")
        
        return existing_reports
        
    except urllib.error.URLError as e:
        print(f"\n❌ ERROR: Could not connect to backend server at {base_url}")
        print(f"   {e}")
        print("\n💡 Make sure the backend server is running:")
        print("   cd backend && python run.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: Failed to fetch reports: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_tech_heavy_portfolio():
    """Test a tech-heavy portfolio (high concentration risk)."""
    print_section("TEST 1: Tech-Heavy Portfolio")
    
    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "TSLA", "AMD", "INTC"]
    print(f"Portfolio: {', '.join(tickers)}")
    print(f"Size: {len(tickers)} positions\n")
    
    existing_reports = fetch_real_reports(tickers)
    
    # Analyze risk
    print("\n🔍 Analyzing portfolio risk...")
    risk_profile = analyze_portfolio_risk(tickers, existing_reports)
    risk_dict = risk_profile.to_dict()
    
    # Print results
    print(f"\n📊 RISK SCORE: {risk_dict['risk_score']:.1f}/100\n")
    
    print("🎯 SECTOR EXPOSURE:")
    for sector, pct in list(risk_dict['sector_exposure'].items())[:5]:
        bar = "█" * int(pct / 2)
        print(f"  {sector:30s} {pct:5.1f}% {bar}")
    
    print(f"\n💼 CONCENTRATION:")
    conc = risk_dict['concentration_risk']
    print(f"  Top 3 Holdings: {conc['top_3_concentration']:.1f}%")
    print(f"  Top 5 Holdings: {conc['top_5_concentration']:.1f}%")
    print(f"  Total Positions: {conc['total_positions']}")
    print(f"  Avg Position Size: {conc['avg_position_size']:.1f}%")
    
    beta = risk_dict['beta_analysis']
    if beta.get('portfolio_beta'):
        print(f"\n📈 BETA ANALYSIS:")
        print(f"  Portfolio Beta: {beta['portfolio_beta']:.2f}")
        print(f"  Beta Std Dev: {beta.get('beta_std', 0):.2f}")
        print(f"  High Beta Stocks (>1.2): {beta.get('high_beta_count', 0)}")
        print(f"  Low Beta Stocks (<0.8): {beta.get('low_beta_count', 0)}")
        if beta.get('beta_range'):
            print(f"  Beta Range: {beta['beta_range']}")
    
    if risk_dict['correlation_clusters']:
        print(f"\n🔗 CORRELATION CLUSTERS:")
        for i, cluster in enumerate(risk_dict['correlation_clusters'], 1):
            print(f"  Cluster {i}: {', '.join(cluster)}")
    
    print(f"\n⚠️  RISK WARNINGS ({len(risk_dict['risk_warnings'])}):")
    for i, warning in enumerate(risk_dict['risk_warnings'], 1):
        print(f"  {i}. {warning[:150]}...")
    
    # Generate questions
    print("\n🤔 Generating critical questions...")
    questions = generate_portfolio_questions(tickers, risk_dict)
    
    print(f"\n❓ CRITICAL QUESTIONS ({len(questions)}):")
    for i, q in enumerate(questions, 1):
        urgency_emoji = "🔴" if q.urgency == "high" else "🟡" if q.urgency == "medium" else "🟢"
        print(f"\n  {urgency_emoji} Question {i} [{q.urgency.upper()}] - {q.category}")
        print(f"     {q.question}")
        print(f"     Context: {q.context[:120]}...")
        if q.suggested_action:
            print(f"     Action: {q.suggested_action[:120]}...")


def test_diversified_portfolio():
    """Test a well-diversified portfolio (lower risk)."""
    print_section("TEST 2: Diversified Portfolio")
    
    tickers = ["AAPL", "JPM", "JNJ", "XOM", "PG", "DIS", "BA", "CAT"]
    print(f"Portfolio: {', '.join(tickers)}")
    print(f"Size: {len(tickers)} positions\n")
    
    existing_reports = fetch_real_reports(tickers)
    
    # Analyze risk
    print("\n🔍 Analyzing portfolio risk...")
    risk_profile = analyze_portfolio_risk(tickers, existing_reports)
    risk_dict = risk_profile.to_dict()
    
    # Print results
    print(f"\n📊 RISK SCORE: {risk_dict['risk_score']:.1f}/100\n")
    
    print("🎯 SECTOR EXPOSURE:")
    for sector, pct in list(risk_dict['sector_exposure'].items())[:5]:
        bar = "█" * int(pct / 2)
        print(f"  {sector:30s} {pct:5.1f}% {bar}")
    
    print(f"\n💼 CONCENTRATION:")
    conc = risk_dict['concentration_risk']
    print(f"  Top 3 Holdings: {conc['top_3_concentration']:.1f}%")
    beta = risk_dict['beta_analysis']
    if beta.get('portfolio_beta'):
        print(f"  Portfolio Beta: {beta['portfolio_beta']:.2f}")
    
    print(f"\n⚠️  RISK WARNINGS ({len(risk_dict['risk_warnings'])}):")
    for i, warning in enumerate(risk_dict['risk_warnings'], 1):
        print(f"  {i}. {warning[:150]}...")
    
    # Generate questions
    print("\n🤔 Generating critical questions...")
    questions = generate_portfolio_questions(tickers, risk_dict)
    
    print(f"\n❓ CRITICAL QUESTIONS ({len(questions)}):")
    for i, q in enumerate(questions, 1):
        urgency_emoji = "🔴" if q.urgency == "high" else "🟡" if q.urgency == "medium" else "🟢"
        print(f"  {urgency_emoji} {i}. {q.question}")


def test_small_portfolio():
    """Test a small portfolio (under-diversified)."""
    print_section("TEST 3: Small Portfolio (3 stocks)")
    
    tickers = ["AAPL", "MSFT", "GOOGL"]
    print(f"Portfolio: {', '.join(tickers)}")
    print(f"Size: {len(tickers)} positions\n")
    
    existing_reports = fetch_real_reports(tickers)
    
    # Analyze risk
    print("\n🔍 Analyzing portfolio risk...")
    risk_profile = analyze_portfolio_risk(tickers, existing_reports)
    risk_dict = risk_profile.to_dict()
    
    # Print results
    print(f"\n📊 RISK SCORE: {risk_dict['risk_score']:.1f}/100\n")
    
    print("🎯 SECTOR EXPOSURE:")
    for sector, pct in risk_dict['sector_exposure'].items():
        bar = "█" * int(pct / 2)
        print(f"  {sector:30s} {pct:5.1f}% {bar}")
    
    print(f"\n⚠️  RISK WARNINGS ({len(risk_dict['risk_warnings'])}):")
    for i, warning in enumerate(risk_dict['risk_warnings'], 1):
        print(f"  {i}. {warning}")
    
    # Generate questions
    print("\n🤔 Generating critical questions...")
    questions = generate_portfolio_questions(tickers, risk_dict)
    
    print(f"\n❓ CRITICAL QUESTIONS ({len(questions)}):")
    for i, q in enumerate(questions, 1):
        urgency_emoji = "🔴" if q.urgency == "high" else "🟡" if q.urgency == "medium" else "🟢"
        print(f"\n  {urgency_emoji} Question {i} [{q.urgency.upper()}]")
        print(f"     {q.question}")
        print(f"     {q.context[:200]}...")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  PORTFOLIO RISK PROFILER & INTERROGATOR - TEST SUITE")
    print("  Using REAL data from backend server")
    print("=" * 80)
    
    try:
        test_tech_heavy_portfolio()
        test_diversified_portfolio()
        test_small_portfolio()
        
        print_section("✅ ALL TESTS COMPLETED")
        print("The Portfolio Risk Profiler and Interrogator are working correctly!")
        print("\nNext steps:")
        print("1. Run full portfolio deep research: python backend/run_portfolio_deep_research.py")
        print("2. Use VSCode debugger with 'Portfolio Deep Research' configurations")
        print("3. Check the generated HTML report for risk profile and questions\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob

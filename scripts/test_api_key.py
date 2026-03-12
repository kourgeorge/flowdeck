#!/usr/bin/env python3
"""
Test script for FlowDeck API key authentication.

This script demonstrates how to use API keys to access FlowDeck endpoints.
It tests various authenticated and public endpoints.

Usage:
    1. Create an API key via the FlowDeck UI (Profile → API Keys)
    2. Set the API_KEY variable below or pass as environment variable
    3. Run: python scripts/test_api_key.py
"""

import os
import sys
import requests
from typing import Dict, Any

# Configuration
BASE_URL = os.environ.get("FLOWDECK_API_URL", "https://flowdeck.biz")
API_KEY = os.environ.get("FLOWDECK_API_KEY", "fd_live_NatyzYD7BEZC-aeRffc7GNJFEVNFASJ3B3DnGWLzk5M")  # Set your API key here or via env var
API_KEY = os.environ.get("FLOWDECK_API_KEY", "fd_live_OxIEUmwK3eJHSAo-cRTuoJpZWz8emQaFrorQksWC8cA")  # Set your API key here or via env var

# ANSI color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {text}{RESET}")


def test_public_endpoint():
    """Test a public endpoint (no authentication required)."""
    print_header("Test 1: Public Endpoint (Stock Quote)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/data/quote/AAPL")
        response.raise_for_status()
        data = response.json()
        
        print_success(f"Successfully fetched AAPL quote")
        print(f"  Current Price: ${data.get('current_price', 'N/A')}")
        print(f"  Daily Change: {data.get('daily_change_percent', 'N/A')}%")
        print(f"  Market Status: {data.get('market_status', 'N/A')}")
        return True
    except Exception as e:
        print_error(f"Failed to fetch quote: {e}")
        return False


def test_user_profile(headers: Dict[str, str]):
    """Test getting user profile with API key."""
    print_header("Test 2: User Profile (Authenticated)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/me", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print_success("Successfully authenticated with API key")
        print(f"  User ID: {data.get('user_id')}")
        print(f"  Email: {data.get('email')}")
        print(f"  Name: {data.get('name', 'Not set')}")
        print(f"  Token Balance: {data.get('token_balance', 0):,} tokens")
        print(f"  Admin: {data.get('is_admin', False)}")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print_error("Authentication failed - Invalid or expired API key")
        else:
            print_error(f"HTTP {e.response.status_code}: {e.response.text}")
        return False
    except Exception as e:
        print_error(f"Failed to fetch profile: {e}")
        return False


def test_user_stats(headers: Dict[str, str]):
    """Test getting user statistics."""
    print_header("Test 3: User Statistics (Authenticated)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/me/stats", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print_success("Successfully fetched user statistics")
        print(f"  Analyses Created: {data.get('analyses_created', 0)}")
        print(f"  Reports Viewed: {data.get('reports_viewed', 0)}")
        print(f"  Tokens Earned: {data.get('tokens_earned_from_views', 0)}")
        print(f"  Subscriptions: {data.get('subscriptions_count', 0)}")
        print(f"  Member Since: {data.get('member_since', 'Unknown')}")
        return True
    except Exception as e:
        print_error(f"Failed to fetch stats: {e}")
        return False


def test_ai_reports(headers: Dict[str, str]):
    """Test getting AI analysis reports."""
    print_header("Test 4: AI Reports (Authenticated)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/data/reports/AAPL", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        report_date = data.get('report_date')
        reports = data.get('reports', {})
        
        if report_date:
            print_success(f"Successfully fetched AI reports for AAPL")
            print(f"  Report Date: {report_date}")
            print(f"  Available Reports: {len(reports)}")
            
            # Show recommendation if available
            ftd = reports.get('final_trade_decision', {})
            if ftd:
                rec = ftd.get('recommendation', 'N/A')
                conf = ftd.get('confidence')
                conf_str = f" ({conf*100:.0f}% confidence)" if conf else ""
                print(f"  Recommendation: {rec}{conf_str}")
        else:
            print_info("No reports available for AAPL yet")
        
        return True
    except Exception as e:
        print_error(f"Failed to fetch reports: {e}")
        return False


def test_chat(headers: Dict[str, str]):
    """Test chat endpoint with AI analyst."""
    print_header("Test 5: AI Chat (Authenticated, Costs Tokens)")
    
    print_info("This test will use tokens from your account")
    
    try:
        payload = {
            "messages": [
                {"role": "user", "content": "What is AAPL's current price?"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/chat",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        
        print_success("Successfully chatted with AI analyst")
        print(f"  Reply: {data.get('reply', 'N/A')[:200]}...")
        print(f"  Tokens Used: {data.get('tokens_used', 0)}")
        print(f"  New Balance: {data.get('balance', 0):,} tokens")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 402:
            print_error("Insufficient token balance")
        else:
            print_error(f"HTTP {e.response.status_code}: {e.response.text}")
        return False
    except Exception as e:
        print_error(f"Failed to chat: {e}")
        return False


def test_api_key_management(headers: Dict[str, str]):
    """Test API key management endpoints."""
    print_header("Test 6: API Key Management (Authenticated)")
    
    try:
        # List existing keys
        response = requests.get(f"{BASE_URL}/api/api-keys", headers=headers)
        response.raise_for_status()
        keys = response.json()
        
        print_success(f"Successfully listed API keys")
        print(f"  Total Keys: {len(keys)}")
        
        for i, key in enumerate(keys[:3], 1):  # Show first 3
            status = "Active" if key.get('is_active') else "Inactive"
            print(f"  {i}. {key.get('name')} ({key.get('key_prefix')}...) - {status}")
        
        if len(keys) > 3:
            print(f"  ... and {len(keys) - 3} more")
        
        return True
    except Exception as e:
        print_error(f"Failed to list API keys: {e}")
        return False


def main():
    """Run all tests."""
    print_header("FlowDeck API Key Test Suite")
    print(f"Base URL: {BASE_URL}")
    
    # Check if API key is set
    if not API_KEY:
        print_error("API_KEY not set!")
        print_info("Please set your API key:")
        print_info("  1. Create a key via FlowDeck UI (Profile → API Keys)")
        print_info("  2. Set FLOWDECK_API_KEY environment variable, or")
        print_info("  3. Edit this script and set the API_KEY variable")
        sys.exit(1)
    
    print_info(f"Using API Key: {API_KEY[:16]}...")
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Run tests
    results = []
    
    # Test 1: Public endpoint (no auth)
    results.append(("Public Endpoint", test_public_endpoint()))
    
    # Test 2-6: Authenticated endpoints
    results.append(("User Profile", test_user_profile(headers)))
    results.append(("User Statistics", test_user_stats(headers)))
    results.append(("AI Reports", test_ai_reports(headers)))
    results.append(("AI Chat", test_chat(headers)))
    results.append(("API Key Management", test_api_key_management(headers)))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {name}: {status}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print_success("All tests passed! API key authentication is working correctly.")
        sys.exit(0)
    else:
        print_error(f"{total - passed} test(s) failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()



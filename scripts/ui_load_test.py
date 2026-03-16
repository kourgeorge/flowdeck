"""
Playwright UI Load Test for Flowdeck

Simulates realistic user interactions with the frontend UI including:
- Browsing the homepage
- Navigating to stock pages
- Viewing reports and charts
- Using the chat feature
- Subscribing to stocks
- Viewing market data

This complements the API load test (locustfile.py) by testing the full UI stack
including React rendering, API calls, and user interactions.

Install:
    pip install playwright pytest-playwright
    playwright install chromium

Run:
    # Single user journey (debug mode)
    python scripts/ui_load_test.py --users 1 --headless false

    # Multiple concurrent users (load test)
    python scripts/ui_load_test.py --users 10 --duration 300

    # With authentication
    python scripts/ui_load_test.py --users 5 --email user@example.com --password yourpass

See docs/STRESS_TEST.md for more details.
"""

import asyncio
import argparse
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
from typing import List, Dict, Any

# Configuration
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "JNJ"]
BASE_URL = "http://localhost:4173"  # Vite dev server default


class UserJourney:
    """Simulates a realistic user journey through the Flowdeck UI."""

    def __init__(self, browser: Browser, user_id: int, email: str = None, password: str = None):
        self.browser = browser
        self.user_id = user_id
        self.email = email
        self.password = password
        self.page: Page = None
        self.metrics: Dict[str, Any] = {
            "user_id": user_id,
            "actions": [],
            "errors": [],
            "start_time": None,
            "end_time": None,
        }

    async def log_action(self, action: str, duration: float = None, success: bool = True):
        """Log an action with timing."""
        log_entry = {
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": duration,
            "success": success,
        }
        self.metrics["actions"].append(log_entry)
        status = "✓" if success else "✗"
        print(f"[User {self.user_id}] {status} {action} ({duration:.0f}ms)" if duration else f"[User {self.user_id}] {status} {action}")

    async def log_error(self, action: str, error: str):
        """Log an error."""
        self.metrics["errors"].append({"action": action, "error": str(error), "timestamp": datetime.now().isoformat()})
        print(f"[User {self.user_id}] ✗ ERROR in {action}: {error}")

    async def measure_action(self, action_name: str, action_func):
        """Measure and log an action's execution time."""
        start = time.time()
        try:
            await action_func()
            duration = (time.time() - start) * 1000
            await self.log_action(action_name, duration, True)
        except Exception as e:
            duration = (time.time() - start) * 1000
            await self.log_action(action_name, duration, False)
            await self.log_error(action_name, str(e))

    async def setup(self):
        """Initialize browser context and page."""
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        self.page = await context.new_page()
        self.metrics["start_time"] = datetime.now().isoformat()

    async def teardown(self):
        """Close browser context."""
        if self.page:
            await self.page.close()
        self.metrics["end_time"] = datetime.now().isoformat()

    async def login(self):
        """Login if credentials provided."""
        if not self.email or not self.password:
            return

        async def do_login():
            await self.page.goto(f"{BASE_URL}/")
            await self.page.wait_for_load_state("networkidle")
            
            # Click login button (adjust selector based on your UI)
            await self.page.click('button:has-text("Sign In")', timeout=5000)
            await self.page.wait_for_timeout(500)
            
            # Fill login form
            await self.page.fill('input[type="email"]', self.email)
            await self.page.fill('input[type="password"]', self.password)
            await self.page.click('button[type="submit"]')
            
            # Wait for redirect after login
            await self.page.wait_for_url("**/dashboard", timeout=10000)

        await self.measure_action("login", do_login)

    async def visit_homepage(self):
        """Visit and interact with homepage."""
        async def do_visit():
            await self.page.goto(f"{BASE_URL}/")
            await self.page.wait_for_load_state("networkidle")
            # Scroll to see more content
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await self.page.wait_for_timeout(1000)

        await self.measure_action("visit_homepage", do_visit)

    async def visit_dashboard(self):
        """Visit dashboard and wait for data to load."""
        async def do_visit():
            await self.page.goto(f"{BASE_URL}/dashboard")
            await self.page.wait_for_load_state("networkidle")
            # Wait for widgets to load
            await self.page.wait_for_selector('[data-testid="stock-widget"], .stock-card, [class*="widget"]', timeout=10000)
            await self.page.wait_for_timeout(1000)

        await self.measure_action("visit_dashboard", do_visit)

    async def view_stock_page(self, ticker: str = None):
        """View a stock detail page."""
        ticker = ticker or random.choice(TICKERS)
        
        async def do_visit():
            await self.page.goto(f"{BASE_URL}/stock/{ticker}")
            await self.page.wait_for_load_state("networkidle")
            # Wait for stock data to load
            await self.page.wait_for_selector('[class*="price"], [class*="quote"]', timeout=10000)
            await self.page.wait_for_timeout(1500)
            
            # Scroll to see charts and reports
            await self.page.evaluate("window.scrollTo(0, 800)")
            await self.page.wait_for_timeout(1000)

        await self.measure_action(f"view_stock_{ticker}", do_visit)

    async def view_report_tabs(self):
        """Click through report tabs if available."""
        async def do_view():
            # Look for report tabs
            tabs = await self.page.query_selector_all('[role="tab"], [class*="tab"]')
            if tabs and len(tabs) > 1:
                # Click a random tab
                tab_index = random.randint(0, min(len(tabs) - 1, 3))
                await tabs[tab_index].click()
                await self.page.wait_for_timeout(1000)

        await self.measure_action("view_report_tabs", do_view)

    async def use_chat(self):
        """Interact with chat feature."""
        async def do_chat():
            # Navigate to chat or open chat panel
            chat_button = await self.page.query_selector('[class*="chat"], button:has-text("Chat")')
            if chat_button:
                await chat_button.click()
                await self.page.wait_for_timeout(500)
                
                # Type a message
                chat_input = await self.page.query_selector('textarea, input[placeholder*="message"], input[placeholder*="chat"]')
                if chat_input:
                    messages = [
                        "What's the market outlook?",
                        f"Tell me about {random.choice(TICKERS)}",
                        "Show me top gainers",
                        "What are the trending stocks?",
                    ]
                    await chat_input.fill(random.choice(messages))
                    await self.page.wait_for_timeout(500)
                    
                    # Submit (press Enter or click send)
                    await chat_input.press("Enter")
                    await self.page.wait_for_timeout(2000)

        await self.measure_action("use_chat", do_chat)

    async def subscribe_to_stock(self, ticker: str = None):
        """Subscribe to a stock."""
        ticker = ticker or random.choice(TICKERS)
        
        async def do_subscribe():
            await self.page.goto(f"{BASE_URL}/stock/{ticker}")
            await self.page.wait_for_load_state("networkidle")
            
            # Find and click subscribe button
            subscribe_btn = await self.page.query_selector('button:has-text("Subscribe"), button:has-text("Follow")')
            if subscribe_btn:
                await subscribe_btn.click()
                await self.page.wait_for_timeout(1000)

        await self.measure_action(f"subscribe_{ticker}", do_subscribe)

    async def view_market_page(self):
        """View market overview page."""
        async def do_visit():
            await self.page.goto(f"{BASE_URL}/market")
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1500)
            
            # Scroll through market data
            await self.page.evaluate("window.scrollTo(0, 600)")
            await self.page.wait_for_timeout(1000)

        await self.measure_action("view_market_page", do_visit)

    async def search_stock(self, ticker: str = None):
        """Use stock search feature."""
        ticker = ticker or random.choice(TICKERS)
        
        async def do_search():
            # Find search input
            search_input = await self.page.query_selector('input[placeholder*="Search"], input[placeholder*="ticker"]')
            if search_input:
                await search_input.fill(ticker)
                await self.page.wait_for_timeout(1000)
                
                # Click first result or press Enter
                first_result = await self.page.query_selector('[class*="search-result"]:first-child, [role="option"]:first-child')
                if first_result:
                    await first_result.click()
                else:
                    await search_input.press("Enter")
                
                await self.page.wait_for_timeout(1500)

        await self.measure_action(f"search_{ticker}", do_search)

    async def run_journey(self, duration_seconds: int = 60):
        """Run a complete user journey with random actions."""
        await self.setup()
        
        try:
            # Login if credentials provided
            if self.email and self.password:
                await self.login()
            
            # Initial page load
            await self.visit_homepage()
            
            # Run random actions for the specified duration
            end_time = time.time() + duration_seconds
            
            actions = [
                self.visit_dashboard,
                lambda: self.view_stock_page(),
                self.view_report_tabs,
                self.view_market_page,
                lambda: self.search_stock(),
            ]
            
            # Add authenticated actions if logged in
            if self.email and self.password:
                actions.extend([
                    self.use_chat,
                    lambda: self.subscribe_to_stock(),
                ])
            
            while time.time() < end_time:
                # Pick a random action
                action = random.choice(actions)
                await action()
                
                # Random wait between actions (simulate user thinking time)
                await asyncio.sleep(random.uniform(2, 5))
        
        finally:
            await self.teardown()
        
        return self.metrics


async def run_load_test(num_users: int, duration: int, headless: bool = True, email: str = None, password: str = None):
    """Run load test with multiple concurrent users."""
    print(f"\n{'='*60}")
    print(f"Starting UI Load Test")
    print(f"Users: {num_users} | Duration: {duration}s | Headless: {headless}")
    print(f"Target: {BASE_URL}")
    print(f"{'='*60}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        
        # Create user journeys
        users = [UserJourney(browser, i + 1, email, password) for i in range(num_users)]
        
        # Run all users concurrently
        start_time = time.time()
        results = await asyncio.gather(*[user.run_journey(duration) for user in users])
        total_time = time.time() - start_time
        
        await browser.close()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Load Test Complete")
        print(f"{'='*60}")
        print(f"Total Duration: {total_time:.2f}s")
        print(f"Users: {num_users}")
        
        total_actions = sum(len(r["actions"]) for r in results)
        total_errors = sum(len(r["errors"]) for r in results)
        success_rate = ((total_actions - total_errors) / total_actions * 100) if total_actions > 0 else 0
        
        print(f"Total Actions: {total_actions}")
        print(f"Total Errors: {total_errors}")
        print(f"Success Rate: {success_rate:.2f}%")
        
        # Calculate average action times
        all_actions = [action for r in results for action in r["actions"] if action["duration_ms"]]
        if all_actions:
            avg_duration = sum(a["duration_ms"] for a in all_actions) / len(all_actions)
            print(f"Average Action Time: {avg_duration:.0f}ms")
        
        # Show errors if any
        if total_errors > 0:
            print(f"\n{'='*60}")
            print("Errors:")
            for r in results:
                for error in r["errors"]:
                    print(f"  [User {r['user_id']}] {error['action']}: {error['error']}")
        
        print(f"{'='*60}\n")
        
        return results


def main():
    parser = argparse.ArgumentParser(description="Flowdeck UI Load Test with Playwright")
    parser.add_argument("--users", type=int, default=1, help="Number of concurrent users (default: 1)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (default: 60)")
    parser.add_argument("--headless", type=str, default="true", help="Run in headless mode (default: true)")
    parser.add_argument("--url", type=str, default="http://localhost:4173", help="Base URL (default: http://localhost:4173)")
    parser.add_argument("--email", type=str, help="Email for authenticated tests")
    parser.add_argument("--password", type=str, help="Password for authenticated tests")
    
    args = parser.parse_args()
    
    global BASE_URL
    BASE_URL = args.url
    
    headless = args.headless.lower() in ("true", "1", "yes")
    
    asyncio.run(run_load_test(
        num_users=args.users,
        duration=args.duration,
        headless=headless,
        email=args.email,
        password=args.password,
    ))


if __name__ == "__main__":
    main()

# Made with Bob

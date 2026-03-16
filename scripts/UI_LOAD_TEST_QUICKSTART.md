# UI Load Testing Quick Start Guide

This guide will help you quickly set up and run UI load tests for Flowdeck.

## Prerequisites

1. **Frontend running**: Your React app should be running (usually on http://localhost:4173 for production build or http://localhost:5173 for dev)
2. **Backend running**: Your API should be running (usually on http://localhost:8002)

## Installation (One-time setup)

```bash
# Install Playwright and dependencies
pip install playwright pytest-playwright

# Install browser binaries (Chromium)
playwright install chromium
```

## Quick Test Scenarios

### 1. Debug Mode - Watch a Single User Journey

Perfect for seeing what the test does and debugging issues:

```bash
python scripts/ui_load_test.py --users 1 --duration 60 --headless false
```

This opens a visible browser window so you can watch the automated interactions.

### 2. Light Load Test - 5 Users for 2 Minutes

Good for initial testing:

```bash
python scripts/ui_load_test.py --users 5 --duration 120
```

### 3. Medium Load Test - 10 Users for 5 Minutes

Realistic load test:

```bash
python scripts/ui_load_test.py --users 10 --duration 300
```

### 4. Heavy Load Test - 20 Users for 10 Minutes

Stress test to find limits:

```bash
python scripts/ui_load_test.py --users 20 --duration 600
```

### 5. Authenticated User Test

Test features that require login:

```bash
python scripts/ui_load_test.py --users 5 --duration 180 \
  --email your-test-user@example.com \
  --password your-test-password
```

## Understanding the Output

The test will show real-time progress:

```
============================================================
Starting UI Load Test
Users: 10 | Duration: 300s | Headless: True
Target: http://localhost:5173
============================================================

[User 1] ✓ visit_homepage (1234ms)
[User 2] ✓ visit_homepage (1156ms)
[User 1] ✓ visit_dashboard (2341ms)
[User 3] ✓ visit_homepage (1289ms)
[User 2] ✓ view_stock_AAPL (1876ms)
...
```

At the end, you'll see a summary:

```
============================================================
Load Test Complete
============================================================
Total Duration: 302.45s
Users: 10
Total Actions: 234
Total Errors: 2
Success Rate: 99.15%
Average Action Time: 1567ms
============================================================
```

## What Gets Tested

Each simulated user randomly performs these actions:

- **Visit homepage** - Loads the landing page
- **Visit dashboard** - Views the main dashboard with widgets
- **View stock pages** - Opens detailed stock information for AAPL, MSFT, GOOGL, etc.
- **View report tabs** - Clicks through different report sections
- **View market page** - Browses market overview
- **Search stocks** - Uses the search functionality
- **Use chat** (if authenticated) - Interacts with the AI assistant
- **Subscribe to stocks** (if authenticated) - Follows/unfollows stocks

## Customization

### Test Different URL

```bash
python scripts/ui_load_test.py --users 10 --duration 300 \
  --url https://your-staging-site.com
```

### Adjust Test Duration

```bash
# Short test (1 minute)
python scripts/ui_load_test.py --users 5 --duration 60

# Long test (30 minutes)
python scripts/ui_load_test.py --users 10 --duration 1800
```

### Run in Visible Mode (for debugging)

```bash
python scripts/ui_load_test.py --users 1 --headless false
```

## Troubleshooting

### "Connection refused" errors

**Problem**: Frontend or backend not running

**Solution**: 
```bash
# Terminal 1: Start backend
cd backend
python run.py

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Run test
python scripts/ui_load_test.py --users 5 --duration 120
```

### "Timeout waiting for selector" errors

**Problem**: UI elements not loading or selectors changed

**Solution**: 
- Run in visible mode to see what's happening: `--headless false`
- Check if the frontend is fully loaded
- Verify the UI hasn't changed significantly

### High error rates

**Problem**: System overloaded or services slow

**Solution**:
- Reduce number of concurrent users
- Check backend logs for errors
- Monitor CPU/memory usage
- Ensure database is responsive

### Playwright not found

**Problem**: Playwright not installed

**Solution**:
```bash
pip install playwright
playwright install chromium
```

## Best Practices

1. **Start small**: Always begin with 1-2 users to verify everything works
2. **Gradual increase**: Slowly increase user count to find your system's limits
3. **Monitor resources**: Watch CPU, memory, and network during tests
4. **Use test accounts**: For authenticated tests, use dedicated test users
5. **Check logs**: Review backend logs after tests for errors or warnings
6. **Run multiple times**: Run tests several times to get consistent results

## Next Steps

1. Run a baseline test with 5 users
2. Gradually increase to 10, 20, 50 users
3. Note when performance degrades
4. Optimize bottlenecks
5. Re-test to verify improvements

## Combining with API Load Tests

For comprehensive testing, run both UI and API tests:

```bash
# Terminal 1: API load test
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002 \
  --users 50 --spawn-rate 5 --run-time 5m --headless

# Terminal 2: UI load test
python scripts/ui_load_test.py --users 10 --duration 300
```

This tests both the backend API performance and the complete user experience simultaneously.

## Getting Help

- Check the full documentation: `docs/STRESS_TEST.md`
- Review the test script: `scripts/ui_load_test.py`
- Playwright documentation: https://playwright.dev/python/

Happy testing! 🚀
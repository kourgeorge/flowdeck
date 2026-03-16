# Load Testing Guide

Flowdeck provides two complementary load testing approaches:

1. **API Load Testing** (Locust) - Tests backend API endpoints directly
2. **UI Load Testing** (Playwright) - Tests the full user experience including frontend rendering

---

## 1. API Load Testing with Locust

Use [Locust](https://locust.io/) to load-test the Flowdeck API with concurrent users hitting heavy endpoints (widgets, ticker page, similar tickers, data API).

### Install

```bash
pip install locust
```

### Run (interactive UI)

1. Start the backend (e.g. `python backend/run.py` or `uvicorn` on port 8002).
2. From the repo root:

   ```bash
   locust -f scripts/locustfile.py --host=http://127.0.0.1:8002
   ```

3. Open http://127.0.0.1:8089 in the browser.
4. Set **Number of users**, **Spawn rate**, then click **Start swarming**.

### Run (headless)

```bash
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002 \
  --users 20 --spawn-rate 4 --run-time 2m --headless
```

- `--users`: total concurrent users.
- `--spawn-rate`: users added per second.
- `--run-time`: e.g. `2m`, `1h`.
- `--headless`: no web UI; results print at the end.

### What gets hit

- **Heaviest**: `/api/tickers/widgets`, `/api/tickers/[ticker]`, `/api/data/similar-tickers/[ticker]`.
- **Data API**: quote, company, extended-info, analyst-recommendations, historical, fundamentals, future-events.
- **Optional auth**: if you set env `STRESS_TEST_TOKEN` to a valid JWT or API key (`fd_live_...`), a small fraction of requests will also call `POST /api/analyses/start` (costs tokens; use a test user with limited balance).

### Auth (optional)

To include authenticated endpoints (e.g. start analysis, reports):

```bash
export STRESS_TEST_TOKEN="your_jwt_or_fd_live_apikey"
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002
```

Get a JWT by signing in via the app and copying the Bearer token from DevTools, or create an API key in the dashboard and use that.

---

## 2. UI Load Testing with Playwright

Use [Playwright](https://playwright.dev/python/) to simulate real users interacting with the frontend UI. This tests the complete stack including React rendering, API calls, and user interactions.

### Install

```bash
pip install playwright pytest-playwright
playwright install chromium
```

### Run (single user, visible browser for debugging)

```bash
python scripts/ui_load_test.py --users 1 --duration 60 --headless false
```

### Run (multiple concurrent users)

```bash
python scripts/ui_load_test.py --users 10 --duration 300
```

**Note**: The default URL is `http://localhost:4173` (production build). If using Vite dev server on port 5173, add `--url http://localhost:5173`

### Run (with authentication)

```bash
python scripts/ui_load_test.py --users 5 --duration 180 \
  --email user@example.com --password yourpassword
```

### Run (against production)

```bash
python scripts/ui_load_test.py --users 20 --duration 600 \
  --url https://your-production-url.com
```

### Command-line options

- `--users`: Number of concurrent browser sessions (default: 1)
- `--duration`: Test duration in seconds (default: 60)
- `--headless`: Run browsers in headless mode - `true` or `false` (default: true)
- `--url`: Base URL to test (default: http://localhost:4173)
- `--email`: Email for authenticated tests (optional)
- `--password`: Password for authenticated tests (optional)

### What gets tested

The UI load test simulates realistic user journeys including:

- **Homepage visits** - Landing page with market overview
- **Dashboard navigation** - Viewing subscribed stocks and widgets
- **Stock page views** - Detailed stock information, charts, and reports
- **Report tab interactions** - Clicking through different report sections
- **Market page browsing** - Market overview and sector performance
- **Stock search** - Using the search functionality
- **Chat interactions** (authenticated) - Asking questions to the AI assistant
- **Stock subscriptions** (authenticated) - Following/unfollowing stocks

Each user performs random actions with realistic wait times between interactions.

### Metrics collected

- Total actions performed
- Success/failure rate
- Average action duration
- Detailed error logs
- Per-user journey statistics

---

## Comparison: API vs UI Load Testing

| Aspect | API Testing (Locust) | UI Testing (Playwright) |
|--------|---------------------|------------------------|
| **What it tests** | Backend API endpoints | Full user experience |
| **Speed** | Very fast (1000+ RPS) | Slower (browser overhead) |
| **Resource usage** | Low | High (browser instances) |
| **Realism** | API-level only | Complete user journey |
| **Best for** | Backend performance | Frontend + backend integration |
| **Concurrent users** | Hundreds to thousands | Tens to hundreds |

### Recommended Testing Strategy

1. **Start with API testing** to establish backend performance baseline
2. **Add UI testing** to validate the complete user experience
3. **Run both** for comprehensive load testing

Example workflow:
```bash
# 1. Test backend API (high load)
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002 \
  --users 100 --spawn-rate 10 --run-time 5m --headless

# 2. Test UI with realistic user behavior (moderate load)
python scripts/ui_load_test.py --users 20 --duration 300

# 3. Test authenticated flows
python scripts/ui_load_test.py --users 10 --duration 180 \
  --email test@example.com --password testpass
```

---

## Tips

- **Start small**: Begin with 1-5 users to verify everything works
- **Monitor resources**: Watch CPU, memory, and network during tests
- **Check logs**: Review backend logs for errors and slow queries
- **Gradual ramp-up**: Increase load gradually to find breaking points
- **Use test data**: For authenticated tests, use dedicated test accounts
- **Production testing**: Always get permission before load testing production
- **Network conditions**: Consider testing with throttled network speeds
- **Browser diversity**: Playwright supports Chrome, Firefox, and Safari

---

## Troubleshooting

### UI tests fail to start
- Ensure frontend is running: `cd frontend && npm run dev`
- Check the URL matches your frontend port (default: 5173)
- Verify Playwright browsers are installed: `playwright install`

### High failure rates
- Check if services are running (backend + frontend)
- Reduce concurrent users
- Increase wait times between actions
- Check network connectivity

### Slow performance
- Close unnecessary applications
- Use headless mode for better performance
- Reduce number of concurrent users
- Check database connection pool settings

# API stress testing

Use [Locust](https://locust.io/) to load-test the Flowdeck API with concurrent users hitting heavy endpoints (widgets, ticker page, similar tickers, data API).

## Install

```bash
pip install locust
```

## Run (interactive UI)

1. Start the backend (e.g. `python backend/run.py` or `uvicorn` on port 8002).
2. From the repo root:

   ```bash
   locust -f scripts/locustfile.py --host=http://127.0.0.1:8002
   ```

3. Open http://127.0.0.1:8089 in the browser.
4. Set **Number of users**, **Spawn rate**, then click **Start swarming**.

## Run (headless)

```bash
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002 \
  --users 20 --spawn-rate 4 --run-time 2m --headless
```

- `--users`: total concurrent users.
- `--spawn-rate`: users added per second.
- `--run-time`: e.g. `2m`, `1h`.
- `--headless`: no web UI; results print at the end.

## What gets hit

- **Heaviest**: `/api/tickers/widgets`, `/api/tickers/[ticker]`, `/api/data/similar-tickers/[ticker]`.
- **Data API**: quote, company, extended-info, analyst-recommendations, historical, fundamentals, future-events.
- **Optional auth**: if you set env `STRESS_TEST_TOKEN` to a valid JWT or API key (`fd_live_...`), a small fraction of requests will also call `POST /api/analyses/start` (costs tokens; use a test user with limited balance).

## Auth (optional)

To include authenticated endpoints (e.g. start analysis, reports):

```bash
export STRESS_TEST_TOKEN="your_jwt_or_fd_live_apikey"
locust -f scripts/locustfile.py --host=http://127.0.0.1:8002
```

Get a JWT by signing in via the app and copying the Bearer token from DevTools, or create an API key in the dashboard and use that.

## Tips

- Start with low users (e.g. 5) and short run (1m) to confirm the backend holds up.
- Watch backend CPU/memory and logs; with `workers=1` the single process serves all requests via thread pool.
- For production-like tests, point `--host` at your deployed URL and use a dedicated test token.

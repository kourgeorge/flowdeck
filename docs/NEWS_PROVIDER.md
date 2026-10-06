# News provider

Flowdeck uses Yahoo Finance Search at
`GET https://query1.finance.yahoo.com/v1/finance/search` with `q`, `newsCount`,
and `quotesCount=0`. The shared `curl_cffi` browser session and a 15-second
request timeout are required. No API key is needed.

On October 6, 2026, the NCP endpoint used by `yfinance.Ticker.news` returned
HTTP 404 for AAPL and MSFT, which yfinance silently converted to empty feeds.
Finance Search returned HTTP 200 and news for both tickers, plus general
queries such as `stock market` and `inflation`.

`backend/data_layer/vendors/yahoo_news.py` owns fetching and article normalization.
App ticker feeds, batch and streaming feeds, briefing context, and morning
watchlist research reach it through `DataGateway` / `MarketDataLayer`.
The legacy `NewsService` uses the same per-ticker cache. Legacy vendor calls
delegate to the adapter, and agent tools use the backend news API.
The existing `yfinance` default for global news now also maps to Finance Search;
explicit alternate vendor settings remain supported.

Search supplies recent results, not an archive. Lookback and explicit date
windows filter returned results; they cannot recover older articles Yahoo no
longer returns. Search usually supplies headlines and links without summaries.
Agent research and morning emails retain the existing best-effort full-text
enrichment. Morning emails still require substantive article evidence, the
movement threshold and event score, and the user's notification preference.

News cache keys include `yahoo-search-v1` to bypass previously cached empty NCP
responses. Transport/schema failures escape the cache and are reported as an
`error` on single-ticker responses or an `errors` map keyed by ticker on batches.
Valid empty searches can still be cached.

NDJSON streams always end with `completed: true`, including empty/failed
searches. Each chunk includes cumulative errors. An article can reappear with
additional matching tickers; consumers must replace articles by UUID or link
instead of appending duplicates. The frontend also detects interrupted streams.

Regression checks:

```sh
PYTHONPATH=backend:. DATA_CACHE_PATH=/tmp/flowdeck-news-tests.sqlite \
  .venv/bin/python -m pytest -q backend/tests/test_yahoo_news.py \
  backend/tests/test_data_layer.py backend/tests/test_data_cache.py \
  backend/tests/test_watchlist_updates.py
node frontend/scripts/check-news-api.cjs
```

The independent briefing suite passes with
`ai_engine.briefing_agent.context_builder._fetch_polymarket_sentiment` mocked to
`{}`; its existing context test otherwise makes live Polymarket requests.

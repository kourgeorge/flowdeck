# Cache Layer

This document describes the shared cache architecture in FlowDeck: what is cached, where the cache is used, and how it relates to the data layer, processing layer, API layer, and persisted reports.

## Purpose

The cache layer is shared infrastructure, not a domain owner.

It exists to:

- reduce repeated third-party fetches
- reduce repeated derived computations
- share runtime state across workers
- keep API and UI latency predictable

The cache is not the source of truth for reports, briefs, executions, or user data.

## Storage backend

The shared cache storage is implemented in [backend/services/data_cache.py](../backend/services/data_cache.py).

Current characteristics:

- SQLite-backed
- per-key TTL
- shared across workers and threads
- JSON-serializable payloads
- also stores analysis runtime state in a separate table

Configured in [backend/config.py](../backend/config.py):

- `DATA_CACHE_PATH`
- `DATA_CACHE_MAX_SIZE`
- `DATA_CACHE_ENABLED`

## Layer model

The runtime layering is:

1. `third_party`
2. `data layer`
3. `processing layer`
4. `API`
5. `UI / Agent`

Caching is a horizontal capability used by multiple layers.

### Data-layer cache

The data layer caches normalized raw payloads fetched from vendors.

Main implementation:

- [backend/data_layer/market.py](../backend/data_layer/market.py)

Examples:

- quotes
- historical OHLCV
- news
- fundamentals
- analyst recommendations
- future events
- insider transactions
- indicators

These use helpers from [backend/services/data_cache.py](../backend/services/data_cache.py) directly.

### Processing-layer cache

The processing layer caches derived artifacts computed from normalized data.

Main implementation:

- [backend/processing/service.py](../backend/processing/service.py)
- [backend/services/platform_cache.py](../backend/services/platform_cache.py)

Current example:

- cached ticker event summaries via `get_ticker_event_summary(...)`

The extraction logic itself remains pure in:

- [backend/processing/event.py](../backend/processing/event.py)

The cache wrapper exists around the orchestration step, not inside the pure extractors.

### Analysis runtime state

The same SQLite cache infrastructure also stores analysis runtime state used across workers.

Examples:

- current analysis status
- running analysis lookup
- stop requests

Main implementation:

- [backend/services/data_cache.py](../backend/services/data_cache.py)
- [backend/services/analysis_service.py](../backend/services/analysis_service.py)

This is cache-backed coordination state, not final report persistence.

## Flow from UI request to cached data

### Raw market data

Example: quote, news, historical prices

1. UI calls [frontend/src/services/api.ts](../frontend/src/services/api.ts).
2. API route receives the request in [backend/routers/data_api.py](../backend/routers/data_api.py).
3. The route calls the shared facade in [backend/data_layer/gateway.py](../backend/data_layer/gateway.py).
4. The gateway delegates to [backend/data_layer/market.py](../backend/data_layer/market.py).
5. The data layer checks the SQLite cache.
6. If present and unexpired, it returns the cached payload.
7. Otherwise it fetches from the vendor, normalizes the payload, stores it in cache, and returns it.

### Derived processing output

Example: stock page Events tab

1. UI calls the existing `/api/data/events/{ticker}` endpoint.
2. The route in [backend/routers/data_api.py](../backend/routers/data_api.py) calls `get_ticker_event_summary(...)`.
3. That service checks the processing cache through [backend/services/platform_cache.py](../backend/services/platform_cache.py).
4. If the derived event summary is cached, it returns it directly.
5. Otherwise it fetches raw inputs through the data layer:
   - historical prices
   - future events
   - insider transactions
   - RSI indicator data
6. Those raw inputs may themselves come from the data-layer cache.
7. The processing layer computes the deterministic event summary, stores it in the cache, and returns it.

This creates two cache levels over the same SQLite store:

- raw input cache
- derived output cache

## Keying and namespacing

There is no central declarative cache registry yet.

Each cached artifact is defined in code by:

- its key or namespace
- its TTL
- its fetch or compute function
- the owning layer

### Data-layer keys

The data layer uses explicit keys such as:

- `quote_full:{ticker}`
- `historical:{ticker}:{period}:{interval}`
- `news:{ticker}:{vendor_version}:{lookback_days}` — `vendor_version` is currently the fixed literal `yfinance`; there is no vendor selection
- `future_events:{ticker}`
- `insider_transactions:{ticker}:{limit}`
- `indicators:{ticker}:{indicator}:{curr_date}:{look_back_days}`

### Processing-layer keys

The processing layer uses [backend/services/platform_cache.py](../backend/services/platform_cache.py) to build namespaced keys.

Example shape:

- `platform:processing_ticker_events:v1:{ticker}:{as_of_date}:{history_period}:{history_interval}:...`

This keeps derived outputs separate from raw data keys while reusing the same cache backend.

## TTL ownership

TTL is chosen by the owning layer.

Examples in [backend/config.py](../backend/config.py):

- `DATA_CACHE_TTL_HISTORICAL`
- `DATA_CACHE_TTL_NEWS`
- `DATA_CACHE_TTL_INSIDER_TRANSACTIONS`
- `DATA_CACHE_TTL_INDICATORS`
- `PROCESSING_CACHE_TTL_TICKER_EVENTS`

The important rule is:

- raw data TTLs belong to the data layer
- derived artifact TTLs belong to the processing layer

## What is not cached here

The cache must not be confused with persisted application data.

Not cache-owned:

- final ticker analysis reports
- saved briefs and brief history
- executions
- user accounts and subscriptions

Those are persisted through application services and the database or report storage layer, for example:

- [backend/services/report_service.py](../backend/services/report_service.py)
- [backend/services/digest_service.py](../backend/services/digest_service.py)

## Adding a new cached artifact

Use this rule:

### If it is normalized raw data from a vendor

Add the cache at the data layer.

Examples:

- new vendor endpoint
- new raw market dataset
- new normalized news feed

### If it is derived from normalized data

Add the cache at the processing layer.

Examples:

- event summaries
- future scoring layers
- report-independent insight snapshots

Recommended pattern:

1. keep the pure computation free of cache logic
2. add a processing service wrapper
3. cache the wrapper output with a namespaced key
4. let API, UI, and agents consume the service instead of recomputing directly

## Current design constraints

- there is no formal cache type registry yet
- all cached payloads share the same SQLite store
- the cache is generic key-value storage, not a typed persistence model
- invalidation is mostly TTL-based today

That is acceptable for the current system, but if the number of cached artifact types grows significantly, a small cache-spec registry may be worth adding later.

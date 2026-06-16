# API Timeout Fix

## Problem
Multiple agents (News Analyst, Market Analyst, Fundamentals Analyst, Valuation Analyst, Technical Analyst) were experiencing frequent timeout errors when calling the backend API at `http://127.0.0.1:8002`:

```
ERROR: News Analyst tool get_insider_transactions failed: HTTPConnectionPool(host='127.0.0.1', port=8002): Read timed out. (read timeout=30)
ERROR: Market Analyst tool get_indicators failed: HTTPConnectionPool(host='127.0.0.1', port=8002): Read timed out. (read timeout=30)
ERROR: Fundamentals Analyst tool get_fundamentals failed: HTTPConnectionPool(host='127.0.0.1', port=8002): Read timed out. (read timeout=30)
ERROR: Valuation Analyst tool get_fundamentals failed: HTTPConnectionPool(host='127.0.0.1', port=8002): Read timed out. (read timeout=30)
ERROR: Technical Analyst tool get_indicators failed: HTTPConnectionPool(host='127.0.0.1', port=8002): Read timed out. (read timeout=30)
```

## Root Cause
The default HTTP request timeout in `ai_engine/tradingagents/datasources/info_service_client.py` was set to 30 seconds, which is insufficient for data-intensive operations such as:

- **get_indicators**: Fetching and calculating technical indicators (RSI, MACD, Bollinger Bands) requires historical price data retrieval and computation
- **get_fundamentals**: Aggregating fundamental data from multiple sources (balance sheet, income statement, cash flow)
- **get_insider_transactions**: Querying and processing insider trading data
- **get_news**: Fetching news from multiple vendors with deduplication
- **get_global_news**: Aggregating macro/global news from various sources

These operations can legitimately take 30-60+ seconds, especially:
- During high load periods
- When cache is cold
- For tickers with extensive data
- When external data vendors are slow

## Solution
Increased timeouts for data-intensive operations:

### Changes Made
**File**: `ai_engine/tradingagents/datasources/info_service_client.py`

1. **Default timeout increased**: 30s → 60s for the base `_get()` function
2. **Extended timeouts for specific operations**: 90s for:
   - `get_news()` - News aggregation from multiple sources
   - `get_insider_transactions()` - Insider trading data processing
   - `get_fundamentals()` - Comprehensive fundamental data
   - `get_indicators()` - Technical indicator calculations
   - `get_global_news()` - Global/macro news aggregation

3. **Existing long timeout preserved**: `get_edgar_filing_content()` already had 120s timeout for SEC filing extraction

### Timeout Strategy
- **Standard operations**: 60s (quote, company info, historical data)
- **Data-intensive operations**: 90s (news, fundamentals, indicators, insider transactions)
- **Heavy LLM operations**: 120s (SEC filing content extraction)

## How to Apply the Fix

### 1. Restart the AI Engine
The AI engine needs to be restarted to pick up the new timeout values:

```bash
# Stop the AI engine (if running as a service)
pkill -f "ai_engine"

# Or if using the start script
./scripts/stop_flowdeck.sh

# Restart
./scripts/start_flowdeck.sh
```

### 2. Verify the Fix
Monitor the logs to confirm timeouts are resolved:

```bash
tail -f backend.log | grep -E "(timeout|ERROR)"
```

You should see:
- Fewer timeout errors
- Successful completion of previously failing operations
- Agents completing their analysis cycles

### 3. If Timeouts Persist
If you still see timeouts after this fix:

1. **Check backend performance**:
   ```bash
   # Monitor backend response times
   curl -w "@-" -o /dev/null -s http://127.0.0.1:8002/api/data/quote/AAPL <<'EOF'
   time_namelookup:  %{time_namelookup}\n
   time_connect:  %{time_connect}\n
   time_starttransfer:  %{time_starttransfer}\n
   time_total:  %{time_total}\n
   EOF
   ```

2. **Check external vendor rate limits**: Some data vendors (Alpha Vantage, Yahoo Finance) may be rate-limiting requests

3. **Consider caching improvements**: Review `backend/services/data_cache.py` for cache hit rates

4. **Increase timeouts further**: If operations legitimately need more time, increase timeouts in `info_service_client.py`

## Impact
- **Positive**: Agents can now complete data-intensive operations without timing out
- **Negative**: Slower operations will take longer to fail (but they should succeed now)
- **Performance**: No performance impact on successful operations; only affects timeout threshold

## Related Files
- `ai_engine/tradingagents/datasources/info_service_client.py` - HTTP client with timeout configuration
- `backend/routers/data_api.py` - Backend API endpoints
- `backend/data_layer/gateway.py` - Data gateway layer
- `backend/services/data_cache.py` - Caching layer to reduce external API calls

## Monitoring
After applying the fix, monitor these metrics:
- Agent success rates (should increase)
- Average operation completion times
- Cache hit rates
- External vendor API usage

## Future Improvements
1. **Adaptive timeouts**: Dynamically adjust timeouts based on operation complexity
2. **Retry logic**: Implement exponential backoff for transient failures
3. **Circuit breaker**: Fail fast when backend is consistently slow
4. **Async operations**: Convert blocking operations to async for better concurrency
5. **Connection pooling**: Reuse HTTP connections to reduce overhead
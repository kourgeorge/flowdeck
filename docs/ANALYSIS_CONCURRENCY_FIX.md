# Analysis Concurrency Fix

## Problem
The AI analysis service allowed multiple simultaneous executions of analysis for the same ticker, which could:
- Waste computational resources
- Cause race conditions
- Lead to duplicate reports
- Charge users multiple times for the same analysis

## Root Cause
The `start_analysis` method had a race condition:
1. Thread A checks if analysis is running for ticker X → Not found
2. Thread B checks if analysis is running for ticker X → Not found (before A registers it)
3. Thread A registers and starts analysis
4. Thread B also registers and starts analysis (duplicate!)

The check (`get_running_analysis_id`) and registration (`running_analyses[analysis_id] = ...`) were not atomic.

## Solution
Implemented thread-safe locking using Python's `threading.Lock()`:

### Changes Made

1. **Added lock to AnalysisService** (`backend/services/analysis_service.py` line 85):
   ```python
   self._lock = threading.Lock()  # Lock to prevent race conditions
   ```

2. **Protected critical section** (lines 110-226):
   - Wrapped the check-and-register logic in `with self._lock:`
   - Ensures only one thread can check and register at a time
   - Analysis is registered in `running_analyses` BEFORE releasing the lock
   - Background thread starts AFTER lock is released

### How It Works Now

1. Thread A acquires lock
2. Thread A checks if analysis exists for ticker X → Not found
3. Thread A registers analysis in `running_analyses`
4. Thread A releases lock
5. Thread A starts background thread
6. Thread B acquires lock (after A releases it)
7. Thread B checks if analysis exists for ticker X → Found! (registered by A)
8. Thread B returns existing analysis_id without starting duplicate

### Key Benefits

- **Prevents duplicate analyses**: Only one analysis per (ticker, date) can run
- **Thread-safe**: Multiple concurrent requests are handled correctly
- **Efficient**: Subsequent requests for same ticker return existing analysis_id
- **Cost-effective**: Users are refunded if they request an already-running analysis (see `backend/main.py` line 767)

## Testing

The implementation was verified to:
- ✓ Have the thread lock properly initialized
- ✓ Have the running_analyses dictionary
- ✓ Use proper Python threading primitives

## Related Code

- **Analysis Service**: `backend/services/analysis_service.py`
- **API Endpoint**: `backend/main.py` (lines 753-769)
- **Token Refund**: `backend/main.py` (line 767) - refunds tokens if analysis already running

## Future Considerations

For distributed deployments (multiple backend instances), consider:
- Redis-based distributed locks
- Database-level locking
- Message queue for analysis requests
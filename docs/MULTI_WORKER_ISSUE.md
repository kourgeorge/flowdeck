# Multi-Worker Deployment Issue

## Critical Problem Identified

The application is configured to run with **4 uvicorn workers** (see `backend/run.py` line 30 and `backend/main.py` line 901):

```python
uvicorn.run("main:app", host="0.0.0.0", port=8002, workers=4, log_config=str(log_config_path))
```

However, the current `AnalysisService` implementation has a **critical flaw** when running with multiple workers.

## The Problem

### Current Architecture (Single Process)

Each worker process creates its **own instance** of `AnalysisService`:

```python
# backend/main.py line 100
analysis_service = AnalysisService()
```

This means:
- **Worker 1** has `analysis_service_1` with its own `running_analyses` dictionary
- **Worker 2** has `analysis_service_2` with its own `running_analyses` dictionary
- **Worker 3** has `analysis_service_3` with its own `running_analyses` dictionary
- **Worker 4** has `analysis_service_4` with its own `running_analyses` dictionary

### What Happens with 4 Workers

**Scenario**: User requests analysis for ticker "AAPL"

1. **Request 1** → Routed to **Worker 1**
   - Worker 1 checks `analysis_service_1.running_analyses` → Not found
   - Worker 1 starts analysis for AAPL
   - Registers in `analysis_service_1.running_analyses`

2. **Request 2** (same ticker) → Routed to **Worker 2**
   - Worker 2 checks `analysis_service_2.running_analyses` → Not found! ❌
   - Worker 2 starts **duplicate analysis** for AAPL
   - Registers in `analysis_service_2.running_analyses`

3. **Request 3** (same ticker) → Routed to **Worker 3**
   - Worker 3 checks `analysis_service_3.running_analyses` → Not found! ❌
   - Worker 3 starts **another duplicate analysis** for AAPL

**Result**: Up to 4 simultaneous analyses for the same ticker! 🔥

### Why the Lock Doesn't Help

The `threading.Lock()` we added only works **within a single process**:

```python
self._lock = threading.Lock()  # Only protects threads in THIS worker process
```

It does NOT protect across different worker processes. Each worker has its own lock that only coordinates threads within that worker.

## Impact

1. **Resource Waste**: Multiple workers running expensive AI analyses for the same ticker
2. **Cost Multiplication**: Users charged multiple times (though refund logic helps)
3. **Database Conflicts**: Multiple workers writing reports with same (ticker, run_id)
4. **Inconsistent Status**: Status queries may hit different workers showing different states

## Solutions

### Option 1: Single Worker (Quick Fix)

**Change**: Set `workers=1` in deployment

```python
# backend/run.py line 30
uvicorn.run("main:app", host="0.0.0.0", port=8002, workers=1, log_config=str(log_config_path))
```

**Pros**:
- Simple, immediate fix
- Current implementation works correctly
- No code changes needed

**Cons**:
- Reduced concurrency for other API endpoints
- Single point of failure
- Cannot scale horizontally

### Option 2: Redis-Based Distributed Lock (Recommended)

**Implementation**: Use Redis for shared state across workers

```python
import redis
from redis.lock import Lock as RedisLock

class AnalysisService:
    def __init__(self, results_dir: str = "results"):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        # ... existing code ...
    
    def start_analysis(self, ticker: str, analysis_date: str, ...):
        ticker = ticker.upper()
        lock_key = f"analysis_lock:{ticker}:{analysis_date}"
        
        # Distributed lock across all workers
        with RedisLock(self.redis_client, lock_key, timeout=300):
            # Check if analysis is running (in Redis)
            existing_key = f"analysis:{ticker}:{analysis_date}"
            existing_id = self.redis_client.get(existing_key)
            
            if existing_id:
                return (existing_id.decode(), True)
            
            # Register new analysis in Redis
            analysis_id = str(uuid.uuid4())
            self.redis_client.setex(existing_key, 3600, analysis_id)
            
            # Store analysis info in Redis
            self.redis_client.hset(f"analysis_info:{analysis_id}", mapping={
                "ticker": ticker,
                "date": analysis_date,
                "status": "running",
                # ... other fields as JSON
            })
            
            # Start background thread
            # ...
```

**Pros**:
- Works with multiple workers
- Enables horizontal scaling
- Shared state visible to all workers
- Industry-standard solution

**Cons**:
- Requires Redis infrastructure
- More complex implementation
- Network latency for lock operations

### Option 3: Database-Based Locking

**Implementation**: Use database table for analysis tracking

```python
# Create table
CREATE TABLE running_analyses (
    analysis_id UUID PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    analysis_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, analysis_date, status) WHERE status = 'running'
);

# In AnalysisService
def start_analysis(self, ticker: str, analysis_date: str, ...):
    with db.begin():
        # Try to insert (will fail if duplicate exists)
        try:
            existing = db.query(RunningAnalysis).filter(
                RunningAnalysis.ticker == ticker,
                RunningAnalysis.analysis_date == analysis_date,
                RunningAnalysis.status == 'running'
            ).first()
            
            if existing:
                return (existing.analysis_id, True)
            
            # Insert new analysis
            analysis = RunningAnalysis(
                analysis_id=analysis_id,
                ticker=ticker,
                analysis_date=analysis_date,
                status='running'
            )
            db.add(analysis)
            db.commit()
        except IntegrityError:
            # Another worker beat us to it
            db.rollback()
            existing = db.query(RunningAnalysis).filter(...).first()
            return (existing.analysis_id, True)
```

**Pros**:
- Uses existing database infrastructure
- No additional dependencies
- ACID guarantees

**Cons**:
- Database overhead for every check
- Slower than in-memory solutions
- Requires database schema changes

### Option 4: Message Queue (Advanced)

**Implementation**: Use Celery/RQ for analysis tasks

```python
# Analysis becomes a Celery task
@celery.app.task(bind=True)
def run_analysis_task(self, ticker, analysis_date, ...):
    # Task ID is unique per invocation
    # Celery handles deduplication
    ...

# In API endpoint
task = run_analysis_task.apply_async(
    args=[ticker, analysis_date, ...],
    task_id=f"analysis:{ticker}:{analysis_date}"  # Prevents duplicates
)
```

**Pros**:
- Proper task queue architecture
- Built-in deduplication
- Better monitoring and retry logic
- Decouples API from analysis execution

**Cons**:
- Major architectural change
- Requires message broker (Redis/RabbitMQ)
- More complex deployment

## Recommended Action Plan

### Immediate (Production Fix)
1. **Set `workers=1`** in deployment configuration
2. Monitor performance and resource usage
3. Document the limitation

### Short-term (1-2 weeks)
1. Implement **Redis-based distributed locking**
2. Test with multiple workers
3. Deploy with `workers=4`

### Long-term (1-3 months)
1. Consider **Celery/task queue** architecture
2. Separate analysis workers from API workers
3. Implement proper job monitoring dashboard

## Testing Multi-Worker Scenarios

```bash
# Test with 4 workers
uvicorn main:app --workers 4 --port 8002

# Simulate concurrent requests
for i in {1..4}; do
  curl -X POST http://localhost:8002/api/analysis/start \
    -H "Content-Type: application/json" \
    -d '{"ticker": "AAPL", "date": "2024-01-15"}' &
done
wait

# Check how many analyses started (should be 1, but currently could be up to 4)
```

## Current Status

✅ **Thread-safe within single worker** (implemented)
❌ **NOT safe across multiple workers** (needs fix)

The threading lock prevents race conditions between threads in the same worker, but does NOT prevent race conditions between different worker processes.

## References

- Current implementation: `backend/services/analysis_service.py`
- Worker configuration: `backend/run.py` line 30, `backend/main.py` line 901
- Related docs: `docs/ANALYSIS_CONCURRENCY_FIX.md`, `docs/STATUS_UPDATE_MECHANISM.md`
# Status Update Mechanism in AnalysisService

## Overview

The `analysis_service.py` implements a real-time status tracking system that allows monitoring the progress of AI analysis as it runs in a background thread. This document explains how the status update mechanism works.

## Architecture

### 1. Shared State via Dictionary

**Location**: Lines 84, 209-226

The core of the status system is the `self.running_analyses` dictionary:

```python
self.running_analyses: Dict[str, Dict] = {}
```

Each analysis creates an entry containing:
- `status`: Overall status ("running", "completed", "error")
- `agent_statuses`: Dictionary tracking each agent's progress
- `reports`: Dictionary storing generated reports
- `messages`: List of analysis messages
- `ticker`, `date`, `run_id`: Analysis metadata
- `progress_callback`: Optional callback for real-time updates

### 2. Background Thread Updates

**Location**: Lines 230-251

The analysis runs in a background thread but updates the **same dictionary object**:

```python
def run_async_analysis():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(self._run_analysis(analysis_id, graph, ticker, analysis_date, analysts))
```

**Key Point**: The `analysis_info` variable in `_run_analysis()` is a **reference** to the dictionary entry in `self.running_analyses`. When the background thread modifies it, those changes are immediately visible to other threads reading the same dictionary.

### 3. Status Update Points

**Location**: Throughout `_run_analysis()` (lines 255-580)

Status updates occur at key milestones:

#### Agent Status Updates
```python
# Line 400: Mark analyst as completed
analysis_info["agent_statuses"]["Market Analyst"] = "completed"

# Lines 404-407: Start next phase
analysis_info["agent_statuses"]["Bull Researcher"] = "in_progress"
analysis_info["agent_statuses"]["Bear Researcher"] = "in_progress"

# Line 417: Trader starts
analysis_info["agent_statuses"]["Trader"] = "in_progress"
```

#### Report Storage
```python
# Line 399: Store completed report
analysis_info["reports"]["market_report"] = content

# Line 424: Store investment plan
analysis_info["reports"]["investment_plan"] = content
```

#### Overall Status
```python
# Line 532: Mark as completed
analysis_info["status"] = "completed"

# Line 574: Mark as error
analysis_info["status"] = "error"
```

### 4. Reading Status

**Location**: Lines 582-584

Other parts of the application can check status at any time:

```python
def get_analysis_status(self, analysis_id: str) -> Optional[Dict]:
    """Get current status of a running analysis."""
    return self.running_analyses.get(analysis_id)
```

This returns the **current state** being continuously updated by the background thread.

### 5. Progress Callbacks

**Location**: Lines 505-509, 556-560

For real-time updates (e.g., WebSocket notifications):

```python
if analysis_info["progress_callback"]:
    try:
        analysis_info["progress_callback"](chunk, analysis_info)
    except Exception:
        pass
```

The callback is invoked after each significant update, enabling push notifications to connected clients.

## Thread Safety

### Why This Works Without Additional Locking

1. **Dictionary operations are atomic** in CPython for basic get/set operations
2. **Each analysis has its own dictionary entry** - no conflicts between analyses
3. **Updates are incremental** - adding/modifying keys, not replacing entire dictionary
4. **Single writer per entry** - only the background thread writes to its analysis entry

### Protected Critical Section

The **only section requiring locking** is the initial check-and-register (lines 113-226):

```python
with self._lock:
    existing_id = self.get_running_analysis_id(ticker, analysis_date)
    if existing_id is not None:
        return (existing_id, True)
    
    # Register new analysis
    self.running_analyses[analysis_id] = {...}
```

After registration:
- Background thread **writes** to its analysis entry
- Other threads **read** from that entry
- No locking needed for status updates

## Status Flow Example

For a typical analysis:

1. **Initial State** (Line 213):
   ```python
   "status": "running"
   ```

2. **Agent Progress** (Lines 400, 414-418, 448, 467-471):
   ```python
   "Market Analyst": "pending" → "in_progress" → "completed"
   "Bull Researcher": "pending" → "in_progress" → "completed"
   "Trader": "pending" → "in_progress" → "completed"
   ```

3. **Reports Generated** (Lines 399, 424, 445, 481):
   ```python
   "reports": {
       "market_report": "...",
       "investment_plan": "...",
       "trader_investment_plan": "...",
       "final_trade_decision": "..."
   }
   ```

4. **Final State** (Line 532):
   ```python
   "status": "completed"
   ```

## Benefits of This Design

1. **Real-time visibility**: Status can be queried at any time
2. **No polling overhead**: Callbacks enable push-based updates
3. **Thread-safe**: Minimal locking, leveraging Python's GIL
4. **Efficient**: No serialization/deserialization overhead
5. **Simple**: Direct dictionary access, no complex synchronization

## Usage Example

```python
# Start analysis
analysis_id, existing = analysis_service.start_analysis(
    ticker="AAPL",
    analysis_date="2024-01-15",
    progress_callback=my_callback
)

# Check status later
status = analysis_service.get_analysis_status(analysis_id)
print(status["status"])  # "running", "completed", or "error"
print(status["agent_statuses"])  # Current agent progress
print(status["reports"])  # Generated reports so far
```

## Related Files

- **Service Implementation**: `backend/services/analysis_service.py`
- **API Endpoint**: `backend/main.py` (WebSocket and HTTP endpoints)
- **Concurrency Fix**: `docs/ANALYSIS_CONCURRENCY_FIX.md`
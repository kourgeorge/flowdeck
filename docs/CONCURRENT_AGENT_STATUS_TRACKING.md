# Concurrent Agent Status Tracking Fix

## Problem

The trading agents system supports **concurrent execution** of analysts via LangGraph's `Send` API (parallel fan-out), but the status tracking structure was designed for **sequential execution**:

- Used `current_agent: str` (single agent)
- Only tracked one active agent at a time
- UI couldn't show multiple agents running simultaneously

## Solution

Changed the status tracking to support multiple concurrent agents:

### Backend Changes (`backend/services/analysis_service.py`)

#### 1. Changed Data Structure
```python
# OLD: Single agent
"current_agent": "Market Analyst"

# NEW: List of agents
"current_agents": ["Market Analyst", "News Analyst", "Social Analyst"]
```

#### 2. Initial Status Setup (lines 254-295)
- Detects if `parallel_analysts` mode is enabled (default: True)
- **Parallel mode**: Sets ALL selected analysts to "in_progress" initially
- **Sequential mode**: Sets only first analyst to "in_progress"

```python
if parallel_analysts and len(analysts) > 1:
    # All selected analysts start in parallel
    current_agents = []
    for analyst_key in analysts:
        if analyst_key in analyst_status_map:
            agent_name = analyst_status_map[analyst_key]
            agent_statuses[agent_name] = "in_progress"
            current_agents.append(agent_name)
else:
    # Sequential mode: only first analyst
    current_agents = [analyst_status_map[first_selected]]
```

#### 3. Status Updates During Execution (lines 558-613)
- When an analyst completes, remove it from `current_agents` list
- In sequential mode, add next analyst to the list
- In parallel mode, all analysts are already in the list

#### 4. Phase Transitions
Updated all phase transitions to use `current_agents` list:

- **Bull/Bear/Research Manager**: `["Bull Researcher", "Bear Researcher", "Research Manager"]`
- **Trader**: `["Trader"]`
- **Risk Analysts**: `["Risky Analyst", "Safe Analyst", "Neutral Analyst"]`
- **Portfolio Manager**: `["Portfolio Manager"]`
- **Completion**: `[]` (empty list)

#### 5. Persistence (lines 131-145)
Updated `_persist_analysis_status()` to save `current_agents` list to SQLite cache:

```python
status_data = {
    "analysis_run_id": analysis_run_id,
    "ticker": analysis_info["ticker"],
    "date": analysis_info["date"],
    "status": analysis_info["status"],
    "agent_statuses": analysis_info.get("agent_statuses", {}),
    "current_agents": analysis_info.get("current_agents", []),  # List instead of string
    "updated_at": datetime.datetime.utcnow().isoformat(),
}
```

## Status Data Structure

### Stored in SQLite Cache (`analysis_status` table)

```json
{
  "analysis_run_id": 12345,
  "ticker": "AAPL",
  "date": "2024-01-15",
  "status": "running",
  "agent_statuses": {
    "Market Analyst": "completed",
    "Social Analyst": "in_progress",
    "News Analyst": "in_progress",
    "Fundamentals Analyst": "in_progress",
    "Technical Analyst": "pending",
    "SEC Analyst": "pending",
    "Bull Researcher": "pending",
    "Bear Researcher": "pending",
    "Research Manager": "pending",
    "Trader": "pending",
    "Risky Analyst": "pending",
    "Neutral Analyst": "pending",
    "Safe Analyst": "pending",
    "Portfolio Manager": "pending"
  },
  "current_agents": ["Social Analyst", "News Analyst", "Fundamentals Analyst"],
  "updated_at": "2024-01-15T14:35:22.123Z"
}
```

## Execution Flow Examples

### Parallel Mode (default)

1. **Start**: All analysts fan out simultaneously
   - `current_agents`: `["Market Analyst", "Social Analyst", "News Analyst", "Fundamentals Analyst", "Technical Analyst", "SEC Analyst"]`
   - All have status "in_progress"

2. **Market Analyst completes first**:
   - `agent_statuses["Market Analyst"]`: "completed"
   - `current_agents`: `["Social Analyst", "News Analyst", "Fundamentals Analyst", "Technical Analyst", "SEC Analyst"]`

3. **All analysts complete**:
   - `current_agents`: `["Bull Researcher", "Bear Researcher", "Research Manager"]`

4. **Debate completes**:
   - `current_agents`: `["Trader"]`

5. **Trader completes**:
   - `current_agents`: `["Risky Analyst", "Safe Analyst", "Neutral Analyst"]`

6. **Risk debate completes**:
   - `current_agents`: `["Portfolio Manager"]`

7. **Final completion**:
   - `current_agents`: `[]`

### Sequential Mode

1. **Start**: Only first analyst
   - `current_agents`: `["Market Analyst"]`

2. **Market completes, News starts**:
   - `current_agents`: `["News Analyst"]`

3. **Each analyst runs one at a time**

## Frontend Integration

The frontend can now:

1. **Display multiple active agents**: Show all agents in `current_agents` list
2. **Show progress accurately**: Display which analysts are running concurrently
3. **Better UX**: Users see the true parallel execution state

### Example UI Display

```
Currently Running:
✓ Market Analyst (completed)
⚙️ Social Analyst (in progress)
⚙️ News Analyst (in progress)  
⚙️ Fundamentals Analyst (in progress)
⏳ Technical Analyst (pending)
⏳ SEC Analyst (pending)
```

## Benefits

✅ **Accurate representation**: Shows true concurrent execution state  
✅ **Backward compatible**: Empty list behaves like null/None  
✅ **Flexible**: Supports both parallel and sequential modes  
✅ **Persistent**: Stored in SQLite cache, visible to all workers  
✅ **Real-time**: Updates as each agent completes

## Configuration

Control execution mode via config:

```python
config = {
    "parallel_analysts": True,  # Default: parallel execution
    # ... other config
}
```

Set to `False` for sequential execution (useful for debugging or resource constraints).

## Testing

To verify the fix:

1. Start an analysis with multiple analysts
2. Check the SQLite cache database:
   ```sql
   SELECT payload FROM analysis_status WHERE type = 'ticker' ORDER BY run_id DESC LIMIT 1;
   ```
3. Verify `current_agents` is a list with multiple agents when parallel mode is enabled
4. Monitor as agents complete and are removed from the list

## Files Modified

- `backend/services/analysis_service.py`: Main implementation
  - Lines 254-295: Initial status setup
  - Lines 131-145: Persistence method
  - Lines 558-613: Analyst completion handling
  - Lines 619-703: Phase transition updates
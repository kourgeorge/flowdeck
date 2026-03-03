# TradingAgent Status Persistence Implementation

## Overview

Implemented file-based status persistence for TradingAgent analyses to solve the issue where UI cannot query status after page refresh when using multiple backend workers.

## Problem Solved

**Issue**: With multiple backend workers (e.g., `--workers 4`), each worker has its own memory space. When a user refreshes the page, the WebSocket may reconnect to a different worker that doesn't have the analysis state in memory.

**Solution**: Write analysis status to a JSON file in the results folder, which all workers can read from the shared filesystem.

## Implementation Details

### Backend Changes

#### 1. Added Status File Management (`backend/services/analysis_service.py`)

**New Methods**:
- `_write_status_file(analysis_id)`: Writes current status to `{results_dir}/status.json`
- `_delete_status_file(analysis_id)`: Deletes status file when analysis completes
- Updated `get_analysis_status(analysis_id)`: Now checks memory first, then searches filesystem

**Status File Location**: `results/{TICKER}/{run_id}/status.json`

**Status File Content**:
```json
{
  "analysis_id": "uuid",
  "ticker": "AAPL",
  "date": "2024-01-15",
  "run_id": "2024-01-15_14-30-00",
  "status": "running",
  "agent_statuses": {
    "Market Analyst": "completed",
    "News Analyst": "in_progress",
    ...
  },
  "current_agent": "News Analyst",
  "updated_at": "2024-01-15T14:35:22.123Z"
}
```

#### 2. Status File Updates at Key Points

Status file is written whenever agent status changes:
- Initial analysis start
- Each analyst completion
- Bull/Bear/Research Manager phase transitions
- Trader completion
- Risk analysts phase transitions
- Portfolio Manager completion
- Final completion or error

Status file is **deleted** when analysis completes or fails (no longer needed).

#### 3. WebSocket Status Request Handler (`backend/main.py`)

Added handler for `"get_status"` message:
```python
elif data == "get_status":
    status = analysis_service.get_analysis_status(analysis_id)
    if status:
        await websocket.send_json({"type": "status", "data": status})
```

### Frontend Changes

#### Updated WebSocket Client (`frontend/src/services/websocket.ts`)

On connection/reconnection, immediately request current status:
```typescript
this.ws.onopen = () => {
  console.log('WebSocket connected');
  this.reconnectAttempts = 0;
  this.send('get_status');  // Request status on connect
  this.emit('open', {});
};
```

## How It Works

### Normal Flow (Same Worker)
1. User starts analysis → Worker 1 stores in memory + writes status.json
2. WebSocket connects to Worker 1 → gets status from memory (fast)
3. Analysis updates → memory updated + status.json updated
4. Analysis completes → status.json deleted

### Page Refresh Flow (Different Worker)
1. User refreshes page → WebSocket reconnects to Worker 2
2. Worker 2 doesn't have analysis in memory
3. WebSocket sends "get_status" on connect
4. Worker 2 searches filesystem, finds status.json, returns it
5. UI updates with current status

### Multiple Workers Flow
```
Worker 1: Running analysis → writes status.json
Worker 2: WebSocket request → reads status.json → returns status
Worker 3: WebSocket request → reads status.json → returns status
Worker 4: API request → reads status.json → returns status
```

## Benefits

✅ **Works with multiple workers**: All workers share filesystem  
✅ **No new dependencies**: Uses existing results folder structure  
✅ **Fast**: Memory-first lookup, file fallback only when needed  
✅ **Automatic cleanup**: Status files deleted when analysis completes  
✅ **Backward compatible**: Existing code continues to work  
✅ **Simple**: Just JSON files, easy to debug and inspect  

## Performance Characteristics

- **Memory lookup**: ~1μs (instant)
- **File lookup**: ~1-5ms (only on reconnection to different worker)
- **File write**: ~1-2ms (non-blocking, happens in background)
- **Disk usage**: ~1KB per running analysis (deleted on completion)

## Limitations

- **Single server only**: Doesn't work across multiple physical servers (would need Redis)
- **File I/O overhead**: Slightly slower than pure memory (but negligible)
- **Stale files**: If backend crashes, status.json may remain (manual cleanup needed)

## Future Enhancements

If you need to scale to multiple servers, consider:
1. **Redis**: Shared memory across servers (see `docs/TRADINGAGENT_RELIABILITY_ALTERNATIVES.md`)
2. **Database**: Persistent storage with automatic cleanup
3. **Message Queue**: Pub/sub for real-time updates across servers

## Testing

To test the implementation:

1. **Start with multiple workers**:
   ```bash
   uvicorn backend.main:app --workers 4
   ```

2. **Start an analysis**:
   - Navigate to stock page
   - Click "Generate Report"
   - Note the analysis_id

3. **Verify status file created**:
   ```bash
   ls results/AAPL/2024-01-15_14-30-00/status.json
   cat results/AAPL/2024-01-15_14-30-00/status.json
   ```

4. **Refresh page during analysis**:
   - Page should reconnect and show current status
   - Check browser console for "WebSocket connected" and status updates

5. **Verify cleanup**:
   - Wait for analysis to complete
   - Verify status.json is deleted
   ```bash
   ls results/AAPL/2024-01-15_14-30-00/status.json  # Should not exist
   ```

## Files Modified

- `backend/services/analysis_service.py`: Added status file management
- `backend/main.py`: Added WebSocket status request handler
- `frontend/src/services/websocket.ts`: Auto-request status on connect

## Rollback

If issues arise, the changes are minimal and can be easily reverted:
1. Remove `_write_status_file()` and `_delete_status_file()` calls
2. Revert `get_analysis_status()` to return only from memory
3. Remove "get_status" handler from WebSocket
4. Remove `send('get_status')` from frontend

The system will work as before (but won't support status recovery across workers).
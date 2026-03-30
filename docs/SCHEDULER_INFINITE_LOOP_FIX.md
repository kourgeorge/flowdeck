# Scheduler Infinite Loop Fix

## Problem Description

The digest scheduler was creating duplicate executions repeatedly, resulting in hundreds of "Running" status entries in the database. The issue manifested as:

- Multiple execution records (IDs 1565-1630+) all with "Running" status
- All created within a short time window (6:00-6:53 AM)
- Same user (kourgeorge@gmail.com)
- Same date (2026-03-30)
- Executions never completing

## Root Cause

The scheduler had a critical flaw in `backend/services/scheduler.py`:

### Issue 1: Race Condition in `_should_run_now()`

```python
# OLD CODE (BUGGY)
if schedule.schedule_type == "daily_digest":
    scheduled_dt = now_local.replace(hour=scheduled_hour, minute=scheduled_minute, ...)
    
    # Check if already ran today
    if schedule.last_executed_at:
        last_local = schedule.last_executed_at.astimezone(tz)
        if last_local.date() == now_local.date():
            return False
    
    # Run if we've reached or passed the scheduled time today
    return now_local >= scheduled_dt  # ⚠️ PROBLEM: Always True after scheduled time!
```

**The Problem**: Once `now_local >= scheduled_dt` becomes true (e.g., at 6:00 AM), it remains true for the entire day. If `last_executed_at` is not updated (due to failure), the scheduler will trigger on **every tick** (every 15 minutes by default).

### Issue 2: Late Update of `last_executed_at`

```python
# OLD CODE (BUGGY)
result, _meta, execution_id, _slot = await run_and_store_digest(...)

if execution_id:
    ok = send_daily_digest_email_to_user(execution_id, user.email)
    if ok:
        schedule.last_executed_at = now_utc  # ⚠️ Only updated on success!
        db.commit()
```

**The Problem**: `last_executed_at` was only updated after:
1. Digest generation succeeded
2. Email sending succeeded

If either step failed, the timestamp was never updated, causing infinite retries.

## The Fix

### Change 1: Update `last_executed_at` Immediately

```python
# NEW CODE (FIXED)
for schedule in schedules:
    try:
        if not _should_run_now(now_utc, schedule, default_tz):
            continue

        # Mark as executed IMMEDIATELY to prevent duplicate runs
        schedule.last_executed_at = now_utc
        db.commit()
        
        # Now attempt the digest generation...
        result, _meta, execution_id, _slot = await run_and_store_digest(...)
```

**Benefits**:
- Prevents duplicate runs even if the process crashes
- Ensures at-most-once execution per schedule period
- Failures are logged but don't cause infinite loops

### Change 2: Enhanced Logging

Added detailed logging to track:
- When schedules are triggered
- User and schedule details
- Success/failure of each step

## Cleanup Script

Created `backend/scripts/cleanup_stuck_executions.py` to handle existing stuck executions:

```bash
# Dry run (shows what would be done)
python backend/scripts/cleanup_stuck_executions.py

# Actually clean up stuck executions older than 2 hours
python backend/scripts/cleanup_stuck_executions.py --no-dry-run --hours 2
```

The script:
1. Finds all executions stuck in "running" status for more than N hours
2. Marks them as "failed" with an explanatory error message
3. Sets `completed_at` timestamp

## Prevention

To prevent this issue in the future:

1. **Always update state before attempting work** - Mark the schedule as executed before running the digest
2. **Use idempotency keys** - The `subject_id` format (`user_id:slot`) helps prevent duplicates
3. **Monitor execution status** - Set up alerts for executions stuck in "running" status
4. **Add execution timeouts** - Consider adding a maximum execution time

## Testing

To verify the fix:

1. Enable the digest scheduler:
   ```bash
   export ENABLE_DIGEST_SCHEDULER=true
   export DIGEST_SCHEDULER_INTERVAL_MINUTES=15
   ```

2. Create a test schedule for a user

3. Monitor logs for:
   - "Starting scheduled digest" messages
   - No duplicate execution_ids for the same schedule period
   - Proper handling of failures

4. Check database:
   ```sql
   SELECT id, execution_type, subject_id, status, created_at 
   FROM executions 
   WHERE execution_type = 'daily_digest' 
   ORDER BY created_at DESC 
   LIMIT 20;
   ```

## Related Files

- `backend/services/scheduler.py` - Main scheduler logic (FIXED)
- `backend/services/digest_service.py` - Digest generation
- `backend/models/db_models.py` - Execution and UserSchedule models
- `backend/scripts/cleanup_stuck_executions.py` - Cleanup utility (NEW)

## Impact

- **Before**: Scheduler could create hundreds of duplicate executions
- **After**: Each schedule runs at most once per period, even on failure
- **Side Effect**: Failed digests won't automatically retry (by design - prevents infinite loops)

If automatic retries are needed in the future, implement them with:
- Exponential backoff
- Maximum retry count
- Separate retry tracking (not via `last_executed_at`)
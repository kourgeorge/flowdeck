# Token Refund Implementation for Failed Executions

## Overview
This document describes the automatic token refund system for failed AI analysis executions and addresses token management consistency.

## Implementation Details

### 1. Automatic Refund on Analysis Failure

When an AI analysis execution fails, the system automatically refunds the deducted tokens (200 tokens) to the user.

**Key Components:**

- **`refund_for_failed_execution()`** in `backend/services/token_service.py`
  - Refunds COST_PER_ANALYSIS (200 tokens) when execution status is 'failed'
  - Prevents duplicate refunds by checking for existing refund transactions
  - Records refund in transaction ledger with proper metadata
  - Keeps execution record for audit trail (doesn't delete it)

- **Analysis Service Integration** in `backend/services/analysis_service.py`
  - Exception handler automatically triggers refund when analysis fails
  - Refund happens after marking execution as 'failed'
  - Includes proper error handling and logging

### 2. Centralized Token Management Architecture

**Question: Does admin token addition update both User table and TokenTransaction table?**

**Answer: NO - The system now uses ONLY the TokenTransaction ledger as the single source of truth.**

#### How It Works (After Refactoring):

1. **Admin adds tokens** via `/api/admin/users/{user_id}/tokens` endpoint
2. Calls `token_service.top_up(user_id, amount, db)`
3. `top_up()` calls `record_transaction()` which:
   - Uses `with_for_update()` to lock the user row (prevents race conditions)
   - **Does NOT update `User.token_balance`** (removed)
   - Creates `TokenTransaction` record ONLY
   - Commits transaction to ledger

4. **Balance is computed dynamically** from TokenTransaction sum:
   ```python
   def get_balance_from_ledger(user_id, db):
       return db.query(func.sum(TokenTransaction.amount))
           .filter(TokenTransaction.user_id == user_id)
           .scalar() or 0
   ```

#### Key Safety Features:

```python
def record_transaction(user_id, amount, transaction_type, db, ...):
    # 1. Lock user row to prevent concurrent modifications
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    
    # 2. Get current balance from ledger (single source of truth)
    current_balance = get_balance_from_ledger(user_id, db)
    
    # 3. Check sufficient balance for debits
    if amount < 0 and current_balance < abs(amount):
        return None
    
    # 4. Create transaction record (this IS the balance update)
    tx = TokenTransaction(
        user_id=user_id,
        amount=amount,
        balance_after=current_balance + amount,  # Snapshot for verification
        transaction_type=transaction_type,
        ...
    )
    db.add(tx)
    
    # 5. Commit transaction
    db.commit()
```

### 3. No Update Anomalies - Single Source of Truth

The refactored system **eliminates** update anomalies through:

1. **Single Source of Truth**: TokenTransaction ledger is the ONLY place balance is stored
2. **No Dual Storage**: `User.token_balance` is NO LONGER UPDATED (can be deprecated/removed)
3. **Computed Balance**: Balance is calculated on-demand from transaction sum
4. **Row Locking**: `with_for_update()` still prevents concurrent modifications
5. **Balance Snapshots**: Each TokenTransaction still records `balance_after` for verification
6. **Atomic Operations**: All token operations go through `record_transaction()`

#### Benefits of Centralized Approach:

- ✅ **Impossible to have sync issues** - only one place stores balance
- ✅ **Complete audit trail** - every balance change is a transaction
- ✅ **Simpler mental model** - no need to keep two tables in sync
- ✅ **Easier debugging** - balance = sum of transactions (always)
- ✅ **Better data integrity** - no risk of User.token_balance drift

### 4. Transaction Types

All token operations are tracked in the ledger:

- `initial_balance` - New user signup
- `purchase` - Token purchase (PayPal, admin top-up)
- `analysis_cost` - Analysis execution deduction
- `digest_cost` - Daily/weekly digest deduction
- `chat_cost` - Chat message deduction
- `view_reward` - Earnings from report views
- `refund` - Refund for failed operations
- `admin_adjustment` - Manual admin corrections

### 5. Refund Flow

```
User initiates analysis
    ↓
200 tokens deducted (analysis_cost transaction)
    ↓
Analysis runs
    ↓
[FAILURE OCCURS]
    ↓
Execution marked as 'failed'
    ↓
System automatically refunds 200 tokens (refund transaction)
    ↓
User balance restored
```

### 6. Testing

Comprehensive tests in `backend/tests/test_token_refund.py` verify:

- ✓ Tokens correctly refunded when execution fails
- ✓ Balance fully restored after refund
- ✓ Refund transaction properly recorded
- ✓ Duplicate refunds prevented
- ✓ Refunds only work for failed executions

## Benefits

1. **User Fairness**: Users don't lose tokens when system fails
2. **Audit Trail**: All token movements tracked in ledger
3. **Data Consistency**: No update anomalies between User and TokenTransaction tables
4. **Transparency**: Users can see refund transactions in their history
5. **Idempotency**: Duplicate refunds prevented automatically

## Future Enhancements

- `refund_for_failed_chat()` function added for future chat refund support
- Can extend to other execution types (digests, etc.)
- Admin dashboard can show refund statistics

## Related Files

- `backend/services/token_service.py` - Token management core
- `backend/services/analysis_service.py` - Analysis execution and refunds
- `backend/routers/admin.py` - Admin token operations
- `backend/tests/test_token_refund.py` - Test suite
- `backend/models/db_models.py` - User and TokenTransaction models
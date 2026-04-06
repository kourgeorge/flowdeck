# Token Accounting Mechanism Review

## Current Implementation Analysis

### ✅ Strengths

#### 1. **Atomic Operations with Row Locking**
```python
user = db.query(User).filter(User.id == user_id).with_for_update().first()
```
- Uses `with_for_update()` for pessimistic locking
- Prevents race conditions in concurrent requests
- Ensures balance updates are serialized per user

#### 2. **Dual Recording**
```python
new_balance = max(0, user.token_balance + amount)
user.token_balance = new_balance  # Update current balance

tx = TokenTransaction(
    amount=amount,
    balance_after=new_balance,  # Snapshot for verification
    ...
)
```
- Updates `User.token_balance` (current state)
- Creates `TokenTransaction` record (audit trail)
- `balance_after` serves as checkpoint

#### 3. **Transaction Boundaries**
- All operations wrapped in try/except with rollback
- Commit/flush control via parameter
- Execution created before transaction (proper ordering)

### ⚠️ Issues Found

#### Issue 1: **Insufficient Balance Check Missing in record_transaction()**

**Problem:**
```python
def record_transaction(...):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        return None
    
    # ❌ No check if user has sufficient balance for negative amounts!
    new_balance = max(0, user.token_balance + amount)
    user.token_balance = new_balance
```

**Impact:**
- If `amount = -200` and `balance = 50`, result is `max(0, 50-200) = 0`
- User gets service but balance just goes to 0 (should fail)
- Callers do check balance, but `record_transaction()` should be defensive

**Fix:**
```python
def record_transaction(...):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        return None
    
    # Check sufficient balance for debits
    if amount < 0 and user.token_balance < abs(amount):
        return None  # Insufficient balance
    
    new_balance = user.token_balance + amount
    if new_balance < 0:
        return None  # Safety check
    
    user.token_balance = new_balance
    ...
```

#### Issue 2: **Balance Verification Not Enforced**

**Problem:**
- No periodic reconciliation between `user.token_balance` and transaction sum
- If a bug causes mismatch, it won't be detected

**Fix:** Add verification function:
```python
def verify_user_balance(user_id: int, db: Session) -> Tuple[bool, str]:
    """
    Verify user's balance matches transaction history.
    Returns (is_valid, message).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "User not found"
    
    # Calculate expected balance from transactions
    transactions = db.query(TokenTransaction).filter(
        TokenTransaction.user_id == user_id
    ).order_by(TokenTransaction.created_at).all()
    
    if not transactions:
        # No transactions yet, should have initial balance
        expected = INITIAL_BALANCE
    else:
        # Sum all transactions
        expected = sum(tx.amount for tx in transactions)
        
        # Also check last transaction's balance_after
        last_tx = transactions[-1]
        if last_tx.balance_after != user.token_balance:
            return False, f"Last transaction balance_after ({last_tx.balance_after}) != current balance ({user.token_balance})"
    
    if expected != user.token_balance:
        return False, f"Calculated balance ({expected}) != stored balance ({user.token_balance})"
    
    return True, "Balance verified"
```

#### Issue 3: **No Idempotency for Duplicate Requests**

**Problem:**
- If a request is retried (network issue, timeout), same operation could be charged twice
- No deduplication mechanism

**Fix:** Add idempotency keys:
```python
class TokenTransaction(Base):
    ...
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    
def record_transaction(..., idempotency_key: Optional[str] = None):
    # Check for duplicate
    if idempotency_key:
        existing = db.query(TokenTransaction).filter(
            TokenTransaction.idempotency_key == idempotency_key
        ).first()
        if existing:
            return existing  # Already processed
    
    # ... rest of function
    tx = TokenTransaction(
        ...
        idempotency_key=idempotency_key,
    )
```

#### Issue 4: **No Negative Balance Prevention at DB Level**

**Problem:**
- Relies on application logic to prevent negative balances
- If bug bypasses checks, database allows negative values

**Fix:** Add CHECK constraint:
```sql
ALTER TABLE users ADD CONSTRAINT check_token_balance_non_negative 
CHECK (token_balance >= 0);
```

### 🔧 Recommended Fixes

#### Priority 1: Critical (Implement Now)

1. **Add balance check in record_transaction()**
```python
# In record_transaction(), before updating balance:
if amount < 0 and user.token_balance < abs(amount):
    return None
```

2. **Add database constraint**
```sql
-- In migration script
ALTER TABLE users ADD CONSTRAINT check_token_balance_non_negative 
CHECK (token_balance >= 0);
```

#### Priority 2: Important (Implement Soon)

3. **Add balance verification function**
- Run periodically (daily cron job)
- Alert on mismatches
- Helps catch bugs early

4. **Add idempotency support**
- Prevents duplicate charges
- Critical for payment operations

#### Priority 3: Nice to Have

5. **Add transaction reversal support**
```python
def reverse_transaction(transaction_id: int, reason: str, db: Session) -> bool:
    """Create compensating transaction to reverse a previous one."""
    original = db.query(TokenTransaction).filter(
        TokenTransaction.id == transaction_id
    ).first()
    if not original:
        return False
    
    # Create reverse transaction
    return record_transaction(
        user_id=original.user_id,
        amount=-original.amount,  # Opposite amount
        transaction_type="reversal",
        related_entity_type="transaction",
        related_entity_id=transaction_id,
        metadata={"reason": reason, "original_tx_id": transaction_id},
        description=f"Reversal: {reason}",
        db=db,
    ) is not None
```

6. **Add transaction limits**
```python
# Max single transaction
MAX_SINGLE_TRANSACTION = 10000

def record_transaction(...):
    if abs(amount) > MAX_SINGLE_TRANSACTION:
        raise ValueError(f"Transaction amount exceeds limit: {abs(amount)} > {MAX_SINGLE_TRANSACTION}")
```

### ✅ What's Already Good

1. **Row-level locking** prevents race conditions
2. **Atomic updates** ensure consistency
3. **Audit trail** provides transparency
4. **Dual token tracking** (platform + LLM) for analytics
5. **Flexible entity linking** via polymorphic associations
6. **Metadata storage** for rich context

### 📊 Testing Recommendations

1. **Concurrent Request Test**
```python
# Simulate 10 concurrent analysis requests from same user
# Verify: Only N succeed where N = balance / COST_PER_ANALYSIS
```

2. **Balance Reconciliation Test**
```python
# After 100 random operations, verify:
# user.token_balance == sum(all transactions)
```

3. **Negative Balance Prevention Test**
```python
# Try to deduct more than balance
# Verify: Operation fails, balance unchanged
```

4. **Transaction Rollback Test**
```python
# Simulate database error mid-transaction
# Verify: Balance not updated, no transaction record created
```

### 🎯 Conclusion

**Current State:** Good foundation with proper locking and atomic operations.

**Critical Fixes Needed:**
1. Add balance check in `record_transaction()`
2. Add database constraint for non-negative balance

**After Fixes:** System will be production-ready with robust token accounting.

The mechanism is fundamentally sound but needs defensive programming improvements to handle edge cases and prevent bugs from causing accounting errors.
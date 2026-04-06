# Data Duplication Analysis & Recommendations

## Current Duplication Issues

### Issue 1: Balance Stored in Two Places

**Current State:**
```
User.token_balance = 1000          (denormalized - current balance)
TokenTransaction.balance_after     (snapshot in each transaction)
SUM(TokenTransaction.amount)       (calculated - should equal balance)
```

**Problem:**
- Three sources of truth for the same data
- Update anomaly risk: If `User.token_balance` is updated without creating a transaction
- Verification needed to ensure consistency

### Issue 2: Metadata Duplication

**Current State:**
```
TokenTransaction.llm_tokens        (stored in transaction)
TokenTransaction.metadata_json     (may also contain llm_tokens info)
ChatMessage.model_metadata_json    (also stores token counts)
```

**Problem:**
- Same LLM token data stored in multiple places
- If chat message metadata is updated, transaction is not
- Inconsistency risk

## Solution Options

### Option A: Remove User.token_balance (Pure Event Sourcing)

**Changes:**
```python
# Remove from User model
class User(Base):
    # token_balance = Column(Integer, ...)  # REMOVE THIS
    
# Calculate balance on demand
def get_balance(user_id: int, db: Session) -> int:
    total = db.query(func.sum(TokenTransaction.amount))\
        .filter(TokenTransaction.user_id == user_id)\
        .scalar()
    return total or 0
```

**Pros:**
- ✅ Single source of truth
- ✅ No update anomalies
- ✅ Always consistent
- ✅ Simpler logic (no dual updates)

**Cons:**
- ❌ Slower balance checks (aggregation query every time)
- ❌ Requires index on (user_id, amount)
- ❌ Breaking change (existing code uses user.token_balance)
- ❌ Performance impact on high-frequency operations

**Performance Impact:**
```sql
-- Current: O(1) lookup
SELECT token_balance FROM users WHERE id = ?

-- With Option A: O(n) aggregation
SELECT SUM(amount) FROM token_transactions WHERE user_id = ?
```

### Option B: Keep User.token_balance, Remove balance_after (Recommended)

**Changes:**
```python
class TokenTransaction(Base):
    # balance_after = Column(Integer, ...)  # REMOVE THIS
    
    # Keep only:
    amount = Column(Integer, nullable=False)
    # Balance can be calculated: previous_balance + amount
```

**Pros:**
- ✅ Removes one duplication point
- ✅ Keeps fast balance lookups
- ✅ Still have audit trail
- ✅ Minimal code changes

**Cons:**
- ❌ Still have User.token_balance duplication
- ❌ Lose checkpoint verification feature
- ❌ Harder to detect corruption

### Option C: Keep Both, Add Strict Enforcement (Current + Improvements)

**Keep current design but add:**

1. **Database Trigger** (if supported):
```sql
CREATE TRIGGER prevent_direct_balance_update
BEFORE UPDATE ON users
FOR EACH ROW
WHEN NEW.token_balance != OLD.token_balance
BEGIN
    -- Only allow updates through stored procedure
    SELECT RAISE(ABORT, 'Direct balance updates not allowed');
END;
```

2. **Application-Level Protection**:
```python
# Make token_balance read-only in ORM
class User(Base):
    _token_balance = Column("token_balance", Integer, nullable=False, default=1000)
    
    @property
    def token_balance(self) -> int:
        return self._token_balance
    
    # No setter - force use of record_transaction()
```

3. **Automated Verification**:
```python
# Run daily via cron
python backend/scripts/verify_token_balances.py
# Alert on any discrepancies
```

**Pros:**
- ✅ Best performance (O(1) lookups)
- ✅ Checkpoint verification (balance_after)
- ✅ No breaking changes
- ✅ Gradual improvement path

**Cons:**
- ❌ Still have duplication
- ❌ Requires discipline
- ❌ Need monitoring

## Recommendation: Hybrid Approach

### Phase 1: Immediate (Keep Current Design + Safeguards)

1. **Add property-based access control**:
```python
class User(Base):
    __tablename__ = "users"
    
    # Make internal
    _token_balance = Column("token_balance", Integer, nullable=False, default=1000)
    
    @property
    def token_balance(self) -> int:
        """Read-only access to token balance."""
        return self._token_balance
    
    def _set_token_balance(self, value: int):
        """Internal use only - called by record_transaction()."""
        self._token_balance = value
```

2. **Update record_transaction() to use internal setter**:
```python
def record_transaction(...):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    ...
    user._set_token_balance(new_balance)  # Use internal method
    ...
```

3. **Add verification to critical paths**:
```python
def get_balance(user_id: int, db: Session) -> int:
    """Get balance with optional verification."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return 0
    
    # In development/staging, verify consistency
    if os.getenv("VERIFY_BALANCES") == "true":
        calculated = db.query(func.sum(TokenTransaction.amount))\
            .filter(TokenTransaction.user_id == user_id)\
            .scalar() or 0
        if calculated != user.token_balance:
            logger.error(f"Balance mismatch for user {user_id}: stored={user.token_balance}, calculated={calculated}")
    
    return user.token_balance
```

### Phase 2: Future (If Performance Allows)

Consider moving to pure event sourcing:

1. **Add materialized view or cache**:
```python
# Redis cache for hot balances
def get_balance_cached(user_id: int, db: Session) -> int:
    cache_key = f"balance:{user_id}"
    cached = redis.get(cache_key)
    if cached:
        return int(cached)
    
    # Calculate from transactions
    balance = db.query(func.sum(TokenTransaction.amount))\
        .filter(TokenTransaction.user_id == user_id)\
        .scalar() or 0
    
    redis.setex(cache_key, 3600, balance)  # Cache for 1 hour
    return balance
```

2. **Gradually migrate code**:
```python
# Old code
balance = user.token_balance

# New code
balance = get_balance(user.id, db)
```

3. **Eventually remove User.token_balance column**

## Decision Matrix

| Criterion | Option A (Pure Event) | Option B (Remove balance_after) | Option C (Current + Safeguards) |
|-----------|----------------------|----------------------------------|----------------------------------|
| Performance | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Consistency | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Simplicity | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Migration Effort | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Verification | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

## Final Recommendation

**Implement Option C (Current + Safeguards) immediately:**

1. ✅ Keep current design (best performance)
2. ✅ Add property-based access control
3. ✅ Add automated verification
4. ✅ Document that balance updates MUST go through record_transaction()
5. ✅ Add monitoring/alerts for discrepancies

**Consider Option A (Pure Event Sourcing) later if:**
- Transaction volume is low enough
- Performance testing shows acceptable latency
- Team prefers stronger consistency guarantees

The current design with safeguards provides the best balance of performance, consistency, and migration safety.
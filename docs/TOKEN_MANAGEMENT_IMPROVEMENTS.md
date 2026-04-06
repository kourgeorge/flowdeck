# Token Management Improvements

## Current State Analysis

After analyzing the codebase, here's the current token management implementation:

### Architecture Overview

**Database Models:**
- `User.token_balance` - Integer field storing platform tokens
- `Execution` - Tracks AI runs (analysis, digests) with earned tokens
- `ReportView` - Tracks unique views for reward system
- `ChatMessage.model_metadata_json` - Stores LLM token usage per message

**Token Service (`backend/services/token_service.py`):**
- Constants: `INITIAL_BALANCE=1000`, `COST_PER_ANALYSIS=200`, `COST_PER_DIGEST=20`
- Reward system: `EARNINGS_PER_UNIQUE_VIEW=1`, `MAX_REWARD_PER_REPORT=400`
- **Two-tier token system:**
  - **LLM Tokens**: Raw token count from language models (input + output tokens)
  - **Platform Tokens**: User-facing currency stored in `User.token_balance`
  - **Conversion Rate**: `LLM_TOKENS_PER_PLATFORM_TOKEN=10000` (10,000 LLM tokens = 1 platform token)

### Current Issues & Gaps

1. **No Transaction History**
   - Token deductions/credits happen directly on `User.token_balance`
   - No audit trail for debugging or user transparency
   - Cannot reconstruct balance history or dispute charges

2. **Limited Observability**
   - No centralized tracking of token consumption patterns
   - Difficult to analyze cost per feature or user behavior
   - No metrics for optimization decisions

3. **Two-Tier Token System Complexity**
   - **LLM Tokens**: Raw usage from language models (e.g., 15,000 input + 5,000 output = 20,000 total)
   - **Platform Tokens**: User-facing currency (20,000 LLM tokens ÷ 10,000 = 2 platform tokens)
   - Chat uses dynamic LLM→platform conversion, but analysis/digest use fixed platform token costs
   - Inconsistent: Users see platform tokens, but chat metadata stores both LLM and platform tokens
   - Need to track both for transparency and cost optimization

4. **Missing Business Intelligence**
   - Cannot calculate revenue per user
   - No cost attribution by feature
   - Limited fraud detection capabilities

5. **No Rate Limiting or Quotas**
   - Users can exhaust balance rapidly
   - No daily/hourly spending limits
   - No warnings before balance depletion

6. **Incomplete Error Handling**
   - Some functions return `(bool, Optional[int])` tuples
   - Others use exceptions
   - Inconsistent rollback behavior

## Recommended Improvements

### 1. Add Transaction Ledger (High Priority)

Create a `TokenTransaction` model to track all balance changes:

```python
class TokenTransaction(Base):
    __tablename__ = "token_transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Platform tokens (what users see and spend)
    amount = Column(Integer, nullable=False)  # Positive for credits, negative for debits
    balance_after = Column(Integer, nullable=False)  # Snapshot for verification
    
    # LLM tokens (for chat operations - tracks actual LLM usage)
    llm_tokens = Column(Integer, nullable=True)  # Raw LLM token count (input + output)
    
    transaction_type = Column(String(32), nullable=False, index=True)
    # Types: "initial_balance", "purchase", "analysis_cost", "digest_cost",
    #        "chat_cost", "view_reward", "refund", "admin_adjustment"
    
    # Generic reference to related entity (polymorphic association)
    related_entity_type = Column(String(32), nullable=True)  # e.g., "execution", "chat_message", "report", "digest"
    related_entity_id = Column(Integer, nullable=True)  # ID of the related entity
    
    # Metadata
    metadata_json = Column(Text, nullable=True)  # Store context: ticker, conversion_rate, model, etc.
    description = Column(String(255), nullable=True)  # Human-readable description
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_token_tx_user_created", "user_id", "created_at"),
        Index("idx_token_tx_type", "transaction_type"),
        Index("idx_token_tx_related_entity", "related_entity_type", "related_entity_id"),
    )
```

**Key Fields:**
- `amount`: Platform tokens deducted/credited (what affects user balance)
- `llm_tokens`: Raw LLM token count (only for chat operations, null for fixed-cost operations)
- `metadata_json`: Stores conversion rate, model name, input/output token breakdown, etc.

**Benefits:**
- Complete audit trail
- User-facing transaction history
- Fraud detection and dispute resolution
- Analytics and reporting

### 2. Unified Token Service with Transactions

Refactor `token_service.py` to use transactions:

```python
def record_transaction(
    user_id: int,
    amount: int,  # Platform tokens (what affects balance)
    transaction_type: str,
    db: Session,
    *,
    llm_tokens: Optional[int] = None,  # Raw LLM token count (for chat)
    execution_id: Optional[int] = None,
    chat_message_id: Optional[int] = None,
    metadata: Optional[Dict] = None,
    description: Optional[str] = None,
    commit: bool = True,
) -> Optional[TokenTransaction]:
    """
    Record a token transaction and update user balance atomically.
    
    Args:
        amount: Platform tokens to add (positive) or deduct (negative)
        llm_tokens: Raw LLM token count (only for chat operations)
        metadata: Additional context (conversion_rate, model, ticker, etc.)
    
    Returns:
        TokenTransaction record or None on failure
    """
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        return None
    
    # Update balance (platform tokens)
    new_balance = max(0, user.token_balance + amount)
    user.token_balance = new_balance
    
    # Create transaction record
    tx = TokenTransaction(
        user_id=user_id,
        amount=amount,  # Platform tokens
        llm_tokens=llm_tokens,  # Raw LLM tokens (null for non-chat operations)
        balance_after=new_balance,
        transaction_type=transaction_type,
        execution_id=execution_id,
        chat_message_id=chat_message_id,
        metadata_json=json.dumps(metadata) if metadata else None,
        description=description,
    )
    db.add(tx)
    
    if commit:
        db.commit()
        db.refresh(tx)
    else:
        db.flush()
    
    return tx

# Refactor existing functions to use transactions:

def top_up(user_id: int, amount: int, db: Session, *, metadata: Optional[Dict] = None) -> bool:
    """
    Add tokens to user's balance via transaction ledger.
    Returns True on success, False on failure.
    """
    if amount <= 0:
        return False
    
    description = f"Token purchase: {amount} tokens"
    tx = record_transaction(
        user_id=user_id,
        amount=amount,
        transaction_type="purchase",
        db=db,
        metadata=metadata,  # Can include: package_id, payment_id, price_usd
        description=description,
    )
    return tx is not None

def deduct_for_analysis(user_id: int, ticker: str, db: Session) -> Tuple[bool, Optional[int]]:
    """
    Deduct COST_PER_ANALYSIS from user via transaction ledger.
    Returns (True, execution_id) on success, (False, None) if insufficient balance.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.token_balance < COST_PER_ANALYSIS:
        return (False, None)
    
    try:
        # Create execution first
        ex_id = record_execution(user_id, "ticker", "ticker", ticker.upper(), db, commit=False)
        
        # Record transaction
        metadata = {"ticker": ticker.upper(), "execution_id": ex_id}
        tx = record_transaction(
            user_id=user_id,
            amount=-COST_PER_ANALYSIS,
            transaction_type="analysis_cost",
            db=db,
            execution_id=ex_id,
            metadata=metadata,
            description=f"Analysis run for {ticker.upper()}",
            commit=False,
        )
        
        if tx:
            db.commit()
            return (True, ex_id)
        else:
            db.rollback()
            return (False, None)
    except Exception:
        db.rollback()
        return (False, None)

def deduct_for_chat(user_id: int, llm_tokens: int, db: Session, *,
                    chat_message_id: Optional[int] = None,
                    model: Optional[str] = None,
                    input_tokens: Optional[int] = None,
                    output_tokens: Optional[int] = None,
                    commit: bool = True) -> bool:
    """
    Deduct chat cost via transaction ledger.
    Tracks both LLM tokens (actual usage) and platform tokens (what user pays).
    
    Args:
        llm_tokens: Total LLM tokens (input + output)
        model: LLM model name (e.g., "gpt-4", "claude-3-opus")
        input_tokens: LLM input tokens (for detailed tracking)
        output_tokens: LLM output tokens (for detailed tracking)
    """
    platform_tokens = llm_tokens_to_platform_tokens(llm_tokens)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.token_balance < 1:
        return False
    
    # Store detailed metadata for transparency and optimization
    metadata = {
        "conversion_rate": LLM_TOKENS_PER_PLATFORM_TOKEN,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    
    tx = record_transaction(
        user_id=user_id,
        amount=-platform_tokens,  # Platform tokens deducted
        llm_tokens=llm_tokens,  # Raw LLM tokens used
        transaction_type="chat_cost",
        db=db,
        chat_message_id=chat_message_id,
        metadata=metadata,
        description=f"Chat message ({llm_tokens:,} LLM tokens → {platform_tokens} platform tokens)",
        commit=commit,
    )
    return tx is not None

def refund_for_execution(user_id: int, execution_id: int, db: Session) -> None:
    """
    Refund COST_PER_ANALYSIS via transaction ledger and remove Execution.
    """
    ex = db.query(Execution).filter(
        Execution.id == execution_id,
        Execution.creator_id == user_id,
    ).first()
    
    if ex:
        metadata = {"execution_id": execution_id, "reason": "duplicate_or_error"}
        record_transaction(
            user_id=user_id,
            amount=COST_PER_ANALYSIS,
            transaction_type="refund",
            db=db,
            execution_id=execution_id,
            metadata=metadata,
            description=f"Refund for execution {execution_id}",
            commit=False,
        )
        db.delete(ex)
        db.commit()
```

### 3. Add Rate Limiting & Quotas

```python
# In token_service.py
DAILY_SPENDING_LIMIT = 5000  # Max tokens per day
HOURLY_SPENDING_LIMIT = 1000  # Max tokens per hour

def check_spending_limit(user_id: int, amount: int, db: Session) -> Tuple[bool, str]:
    """
    Check if user can spend 'amount' tokens without exceeding limits.
    Returns (allowed, reason).
    """
    now = datetime.now(timezone.utc)
    
    # Check hourly limit
    hour_ago = now - timedelta(hours=1)
    hourly_spent = db.query(func.sum(TokenTransaction.amount))\
        .filter(
            TokenTransaction.user_id == user_id,
            TokenTransaction.amount < 0,  # Only debits
            TokenTransaction.created_at >= hour_ago
        ).scalar() or 0
    
    if abs(hourly_spent) + amount > HOURLY_SPENDING_LIMIT:
        return False, f"Hourly limit ({HOURLY_SPENDING_LIMIT} tokens) exceeded"
    
    # Check daily limit
    day_ago = now - timedelta(days=1)
    daily_spent = db.query(func.sum(TokenTransaction.amount))\
        .filter(
            TokenTransaction.user_id == user_id,
            TokenTransaction.amount < 0,
            TokenTransaction.created_at >= day_ago
        ).scalar() or 0
    
    if abs(daily_spent) + amount > DAILY_SPENDING_LIMIT:
        return False, f"Daily limit ({DAILY_SPENDING_LIMIT} tokens) exceeded"
    
    return True, ""
```

### 4. Enhanced Cost Tracking with Two-Tier Token System

The transaction ledger tracks both LLM tokens and platform tokens for complete transparency:

**For Chat Operations:**
```python
# Example: User sends a message that uses 15,000 LLM tokens
# Conversion: 15,000 ÷ 10,000 = 1.5 → rounds up to 2 platform tokens

metadata = {
    "conversion_rate": 10000,  # LLM_TOKENS_PER_PLATFORM_TOKEN
    "model": "gpt-4-turbo",
    "input_tokens": 10000,  # Prompt + context
    "output_tokens": 5000,  # Response
    "session_id": session_id,
}

# Transaction record:
# - amount: -2 (platform tokens deducted from balance)
# - llm_tokens: 15000 (actual LLM usage)
# - description: "Chat message (15,000 LLM tokens → 2 platform tokens)"
```

**For Fixed-Cost Operations (Analysis/Digest):**
```python
# Analysis costs 200 platform tokens (fixed price)
# No LLM token tracking needed (llm_tokens = null)

metadata = {
    "ticker": "AAPL",
    "analysis_type": "deep_research",
    "execution_id": execution_id,
}

# Transaction record:
# - amount: -200 (platform tokens)
# - llm_tokens: null (fixed-cost operation)
# - description: "Analysis run for AAPL"
```

**Benefits of Dual Tracking:**
- Users see simple platform token costs
- Admins can analyze actual LLM usage and costs
- Can optimize conversion rate based on real usage patterns
- Detect inefficient prompts (high LLM tokens for low value)
- Calculate true cost per feature (LLM API costs vs platform token revenue)

### 5. User-Facing API Endpoints

Add endpoints for transparency:

```python
# GET /api/tokens/balance
# GET /api/tokens/transactions?limit=50&offset=0
# GET /api/tokens/usage-stats  # Daily/weekly breakdown
```

### 6. Admin Tools

```python
# POST /api/admin/tokens/adjust
# - Add/remove tokens with reason
# - Refund specific transactions
# - View user spending patterns
```

### 7. Monitoring & Alerts

```python
# Alert when:
# - User balance < 100 tokens
# - Unusual spending patterns detected
# - Daily spending limit approaching
# - System-wide token consumption spikes
```

## Implementation Priority

### Phase 1: Foundation (Week 1)
1. Create `TokenTransaction` model and migration
2. Refactor `token_service.py` to use transactions
3. Update all deduction/credit functions
4. Add transaction history API endpoint

### Phase 2: Safety & Limits (Week 2)
1. Implement rate limiting
2. Add spending quotas
3. Add low balance warnings
4. Improve error handling consistency

### Phase 3: Analytics & UX (Week 3)
1. Add usage statistics endpoint
2. Create admin dashboard for token management
3. Add user-facing transaction history UI
4. Implement cost breakdown by feature

### Phase 4: Optimization (Week 4)
1. Add caching for balance checks
2. Optimize transaction queries
3. Add background jobs for analytics
4. Implement predictive balance warnings

## Migration Strategy

1. **Create transaction table** - No downtime
2. **Dual-write period** - Write to both old and new system
3. **Backfill historical data** - Reconstruct from Execution records
4. **Switch reads** - Start reading from transactions
5. **Remove old code** - Clean up after validation

## Testing Checklist

- [ ] Transaction atomicity (concurrent requests)
- [ ] Balance consistency after failures
- [ ] Rate limiting edge cases
- [ ] Transaction history pagination
- [ ] Cost calculation accuracy
- [ ] Refund scenarios
- [ ] Admin adjustment workflows
- [ ] Performance under load

## Metrics to Track

- Average tokens per user per day
- Cost per feature (chat, analysis, digest)
- Token purchase conversion rate
- Balance depletion rate
- Refund frequency
- Rate limit hit rate

## Security Considerations

1. **Transaction immutability** - Never delete transactions, only add compensating entries
2. **Audit logging** - Log all admin adjustments with reason
3. **Balance verification** - Periodic reconciliation jobs
4. **Fraud detection** - Alert on suspicious patterns
5. **Access control** - Strict permissions on admin endpoints

## Cost Model Recommendations

Consider dynamic pricing based on:
- Time of day (off-peak discounts)
- User tier (premium users get better rates)
- Feature complexity (deep research costs more)
- Market conditions (adjust based on LLM API costs)

## Future Enhancements

1. **Token packages with bonuses** - Buy 1000, get 1100
2. **Subscription plans** - Monthly token allowance
3. **Referral rewards** - Earn tokens for invites
4. **Achievement system** - Bonus tokens for milestones
5. **Token gifting** - Transfer between users
6. **Rollover limits** - Unused tokens expire or roll over
# Database Migration Plan

## New Table: `token_transactions`

### SQL Schema

```sql
CREATE TABLE token_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    
    -- Platform tokens (what users see and spend)
    amount INTEGER NOT NULL,  -- Positive for credits, negative for debits
    balance_after INTEGER NOT NULL,  -- Snapshot for verification
    
    -- LLM tokens (for chat operations - tracks actual LLM usage)
    llm_tokens INTEGER NULL,  -- Raw LLM token count (input + output)
    
    transaction_type VARCHAR(32) NOT NULL,
    
    -- Generic reference to related entity (polymorphic association)
    related_entity_type VARCHAR(32) NULL,  -- e.g., "execution", "chat_message", "report", "digest"
    related_entity_id INTEGER NULL,  -- ID of the related entity
    
    -- Metadata and description
    metadata_json TEXT NULL,
    description VARCHAR(255) NULL,
    
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_token_tx_user_created ON token_transactions(user_id, created_at);
CREATE INDEX idx_token_tx_type ON token_transactions(transaction_type);
CREATE INDEX idx_token_tx_related_entity ON token_transactions(related_entity_type, related_entity_id);
```

### Alembic Migration Script

```python
"""add_token_transactions_table

Revision ID: add_token_transactions
Revises: <previous_revision>
Create Date: 2026-04-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_token_transactions'
down_revision = '<previous_revision>'
branch_labels = None
depends_on = None


def upgrade():
    # Create token_transactions table
    op.create_table(
        'token_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('llm_tokens', sa.Integer(), nullable=True),
        sa.Column('transaction_type', sa.String(32), nullable=False),
        sa.Column('related_entity_type', sa.String(32), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_token_tx_user_created', 'token_transactions', ['user_id', 'created_at'])
    op.create_index('idx_token_tx_type', 'token_transactions', ['transaction_type'])
    op.create_index('idx_token_tx_related_entity', 'token_transactions', ['related_entity_type', 'related_entity_id'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_token_tx_related_entity', 'token_transactions')
    op.drop_index('idx_token_tx_type', 'token_transactions')
    op.drop_index('idx_token_tx_user_created', 'token_transactions')
    
    # Drop table
    op.drop_table('token_transactions')
```

## Existing Tables: No Changes Required

The following existing tables remain unchanged:
- `users` - Already has `token_balance` column
- `executions` - Already tracks AI runs
- `chat_messages` - Already has `model_metadata_json`
- `report_views` - Already tracks unique views

## Data Backfill Strategy

After creating the `token_transactions` table, optionally backfill historical data:

```python
"""
Backfill script: Reconstruct transaction history from existing data
Run after migration: python backend/scripts/backfill_token_transactions.py
"""

from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models.db_models import User, Execution, TokenTransaction

def backfill_transactions():
    db = SessionLocal()
    try:
        # 1. Create initial balance transactions for all users
        users = db.query(User).all()
        for user in users:
            tx = TokenTransaction(
                user_id=user.id,
                amount=1000,  # INITIAL_BALANCE
                balance_after=1000,
                transaction_type="initial_balance",
                description="Initial balance (backfilled)",
                created_at=user.created_at,
            )
            db.add(tx)
        
        # 2. Create transactions from executions (analysis/digest costs)
        executions = db.query(Execution).order_by(Execution.created_at).all()
        for ex in executions:
            cost = 200 if ex.execution_type == "ticker" else 20  # COST_PER_ANALYSIS or COST_PER_DIGEST
            
            # Get user's balance at this point (simplified - would need to calculate properly)
            user = db.query(User).filter(User.id == ex.creator_id).first()
            if not user:
                continue
            
            tx = TokenTransaction(
                user_id=ex.creator_id,
                amount=-cost,
                balance_after=user.token_balance,  # Current balance (approximation)
                transaction_type=f"{ex.execution_type}_cost",
                execution_id=ex.id,
                metadata_json=json.dumps({"ticker": ex.subject_id}) if ex.execution_type == "ticker" else None,
                description=f"Backfilled: {ex.execution_type} for {ex.subject_id}",
                created_at=ex.created_at,
            )
            db.add(tx)
        
        db.commit()
        print(f"Backfilled transactions for {len(users)} users and {len(executions)} executions")
    
    except Exception as e:
        db.rollback()
        print(f"Backfill failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill_transactions()
```

## Migration Checklist

- [ ] Create migration script with Alembic
- [ ] Test migration on development database
- [ ] Review indexes for query performance
- [ ] Run migration on staging environment
- [ ] Verify foreign key constraints work correctly
- [ ] Test rollback procedure
- [ ] Optional: Run backfill script for historical data
- [ ] Deploy to production during low-traffic window
- [ ] Monitor database performance after migration
- [ ] Update application code to use new transaction ledger

## Rollback Plan

If issues occur:
1. Stop application servers
2. Run `alembic downgrade -1` to drop the table
3. Restart application (will use old token_service.py)
4. Investigate and fix issues
5. Re-run migration when ready

---

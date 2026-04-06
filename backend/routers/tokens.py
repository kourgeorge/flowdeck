"""
Token transaction API endpoints.
Provides transaction history, usage statistics, and balance information.
"""

from typing import Any, Dict
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User, Usage
from services import token_service
from services.usage_service import get_user_usage_history

router = APIRouter(prefix="/api/tokens", tags=["Tokens"])


# Schemas

class UsageOut(BaseModel):
    id: int
    amount: int
    balance_after: int
    llm_tokens: Optional[int]
    transaction_type: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[int]
    description: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class TokenBalanceResponse(BaseModel):
    balance: int
    user_id: int


class UsageResponse(BaseModel):
    transactions: List[UsageOut]
    total: int
    limit: int
    offset: int


class UsageStatsResponse(BaseModel):
    total_spent: int
    total_earned: int
    net_balance_change: int
    by_type: dict  # {transaction_type: amount}
    period_days: int


class TokenUsageBreakdown(BaseModel):
    chat_cost: int
    analysis_cost: int
    digest_cost: int
    purchases: int
    rewards: int
    total_llm_tokens: Optional[int]


class UsageOperationItem(BaseModel):
    kind: str
    title: str
    subject_label: str
    status: str
    platform_tokens: Optional[int]
    llm_tokens: Optional[int]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost_usd: Optional[float]
    created_at: Optional[str]
    execution_id: Optional[int]
    chat_turn_id: Optional[int]
    chat_session_id: Optional[int]
    tools_called: Optional[int]


class UsageSummary(BaseModel):
    period_days: int
    total_operations: int
    total_platform_tokens: int
    total_llm_tokens: int
    analysis_count: int
    analysis_platform_tokens: int
    analysis_llm_tokens: int
    chat_count: int
    chat_platform_tokens: int
    chat_llm_tokens: int
    digest_count: int
    digest_platform_tokens: int
    digest_llm_tokens: int


class UsageHistoryResponse(BaseModel):
    summary: UsageSummary
    items: List[UsageOperationItem]
    returned_operations: int


# Endpoints

@router.get("/balance", response_model=TokenBalanceResponse)
def get_token_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current token balance for the authenticated user."""
    balance = token_service.get_balance(current_user.id, db)
    return TokenBalanceResponse(balance=balance, user_id=current_user.id)


@router.get("/transactions", response_model=UsageResponse)
def get_usage_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    transaction_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get transaction history for the authenticated user.
    
    Query parameters:
    - limit: Number of transactions to return (1-100, default 50)
    - offset: Number of transactions to skip (for pagination)
    - transaction_type: Filter by type (purchase, analysis_cost, chat_cost, etc.)
    """
    query = db.query(Usage).filter(
        Usage.user_id == current_user.id
    )
    
    if transaction_type:
        query = query.filter(Usage.transaction_type == transaction_type)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    transactions = query.order_by(desc(Usage.created_at))\
        .limit(limit)\
        .offset(offset)\
        .all()

    # Convert to response format
    transactions_out = [
        UsageOut(
            id=tx.id,
            amount=tx.amount,
            balance_after=tx.balance_after,
            llm_tokens=tx.llm_tokens,
            transaction_type=tx.transaction_type,
            related_entity_type=tx.related_entity_type,
            related_entity_id=tx.related_entity_id,
            description=tx.description,
            created_at=tx.created_at.isoformat() if tx.created_at else None,
        )
        for tx in transactions
    ]
    
    return UsageResponse(
        transactions=transactions_out,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/usage-stats", response_model=UsageStatsResponse)
def get_usage_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get token usage statistics for the authenticated user.
    
    Query parameters:
    - days: Number of days to analyze (1-365, default 30)
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get transactions in the period
    transactions = db.query(Usage).filter(
        Usage.user_id == current_user.id,
        Usage.created_at >= cutoff_date
    ).all()
    
    # Calculate statistics
    total_spent = sum(abs(tx.amount) for tx in transactions if tx.amount < 0)
    total_earned = sum(tx.amount for tx in transactions if tx.amount > 0)
    net_balance_change = sum(tx.amount for tx in transactions)
    
    # Group by transaction type
    by_type = {}
    for tx in transactions:
        tx_type = tx.transaction_type
        if tx_type not in by_type:
            by_type[tx_type] = 0
        by_type[tx_type] += tx.amount
    
    return UsageStatsResponse(
        total_spent=total_spent,
        total_earned=total_earned,
        net_balance_change=net_balance_change,
        by_type=by_type,
        period_days=days
    )


@router.get("/usage-breakdown", response_model=TokenUsageBreakdown)
def get_usage_breakdown(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed breakdown of token usage by category.
    
    Query parameters:
    - days: Number of days to analyze (1-365, default 30)
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Aggregate by transaction type
    results = db.query(
        Usage.transaction_type,
        func.sum(Usage.amount).label('total_amount'),
        func.sum(Usage.llm_tokens).label('total_llm_tokens')
    ).filter(
        Usage.user_id == current_user.id,
        Usage.created_at >= cutoff_date
    ).group_by(
        Usage.transaction_type
    ).all()
    
    # Build breakdown
    breakdown = {
        "chat_cost": 0,
        "analysis_cost": 0,
        "digest_cost": 0,
        "purchases": 0,
        "rewards": 0,
        "total_llm_tokens": 0,
    }
    
    for tx_type, total_amount, total_llm in results:
        if tx_type == "chat_cost":
            breakdown["chat_cost"] = abs(total_amount or 0)
            breakdown["total_llm_tokens"] = total_llm or 0
        elif tx_type == "analysis_cost":
            breakdown["analysis_cost"] = abs(total_amount or 0)
        elif tx_type == "digest_cost":
            breakdown["digest_cost"] = abs(total_amount or 0)
        elif tx_type == "purchase":
            breakdown["purchases"] = total_amount or 0
        elif tx_type == "view_reward":
            breakdown["rewards"] = total_amount or 0
    
    return TokenUsageBreakdown(**breakdown)


@router.get("/usage-history", response_model=UsageHistoryResponse)
def get_usage_history(
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return exact per-operation token usage for the authenticated user.

    Includes:
    - analysis executions
    - chat turns
    - digest operations
    """
    payload: Dict[str, Any] = get_user_usage_history(
        db,
        current_user.id,
        days=days,
        limit=limit,
    )
    return UsageHistoryResponse(**payload)

# Made with Bob

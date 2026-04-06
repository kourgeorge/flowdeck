"""
Token transaction API endpoints.
Provides transaction history, usage statistics, and balance information.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.db_models import User, TokenTransaction
from services import token_service

router = APIRouter(prefix="/api/tokens", tags=["Tokens"])


# Schemas

class TokenTransactionOut(BaseModel):
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


class TokenTransactionsResponse(BaseModel):
    transactions: List[TokenTransactionOut]
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


# Endpoints

@router.get("/balance", response_model=TokenBalanceResponse)
def get_token_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current token balance for the authenticated user."""
    balance = token_service.get_balance(current_user.id, db)
    return TokenBalanceResponse(balance=balance, user_id=current_user.id)


@router.get("/transactions", response_model=TokenTransactionsResponse)
def get_token_transactions(
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
    query = db.query(TokenTransaction).filter(
        TokenTransaction.user_id == current_user.id
    )
    
    if transaction_type:
        query = query.filter(TokenTransaction.transaction_type == transaction_type)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    transactions = query.order_by(desc(TokenTransaction.created_at))\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    # Convert to response format
    transactions_out = [
        TokenTransactionOut(
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
    
    return TokenTransactionsResponse(
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
    transactions = db.query(TokenTransaction).filter(
        TokenTransaction.user_id == current_user.id,
        TokenTransaction.created_at >= cutoff_date
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
        TokenTransaction.transaction_type,
        func.sum(TokenTransaction.amount).label('total_amount'),
        func.sum(TokenTransaction.llm_tokens).label('total_llm_tokens')
    ).filter(
        TokenTransaction.user_id == current_user.id,
        TokenTransaction.created_at >= cutoff_date
    ).group_by(
        TokenTransaction.transaction_type
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

# Made with Bob

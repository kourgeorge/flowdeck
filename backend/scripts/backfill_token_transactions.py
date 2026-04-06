#!/usr/bin/env python3
"""
Backfill script: Reconstruct transaction history from existing data.
Run from repo root: python backend/scripts/backfill_token_transactions.py

This script creates transaction records for:
1. Initial balances for all users
2. Historical executions (analysis and digest costs)
3. View rewards (if needed)

Note: This is a best-effort reconstruction. Exact historical balances may not be recoverable.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import SessionLocal
from models.db_models import User, Execution, TokenTransaction
from services.token_service import INITIAL_BALANCE, COST_PER_ANALYSIS, COST_PER_DIGEST

def backfill_transactions():
    """Backfill transaction history from existing data."""
    
    print("Starting token transactions backfill...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Check if transactions already exist
        existing_count = db.query(TokenTransaction).count()
        if existing_count > 0:
            print(f"⚠️  Warning: {existing_count} transactions already exist.")
            response = input("Continue anyway? This may create duplicates. (y/N): ")
            if response.lower() != 'y':
                print("Aborted.")
                return
        
        # 1. Create initial balance transactions for all users
        print("\n1. Creating initial balance transactions...")
        users = db.query(User).all()
        initial_count = 0
        
        for user in users:
            # Check if user already has an initial_balance transaction
            existing_initial = db.query(TokenTransaction).filter(
                TokenTransaction.user_id == user.id,
                TokenTransaction.transaction_type == "initial_balance"
            ).first()
            
            if existing_initial:
                continue
            
            tx = TokenTransaction(
                user_id=user.id,
                amount=INITIAL_BALANCE,
                balance_after=INITIAL_BALANCE,
                transaction_type="initial_balance",
                description="Initial balance (backfilled)",
                created_at=user.created_at,
            )
            db.add(tx)
            initial_count += 1
        
        db.commit()
        print(f"✓ Created {initial_count} initial balance transactions")
        
        # 2. Create transactions from executions (analysis/digest costs)
        print("\n2. Creating transactions from historical executions...")
        executions = db.query(Execution).order_by(Execution.created_at).all()
        analysis_count = 0
        digest_count = 0
        
        for ex in executions:
            # Check if transaction already exists for this execution
            existing_tx = db.query(TokenTransaction).filter(
                TokenTransaction.related_entity_type == "execution",
                TokenTransaction.related_entity_id == ex.id
            ).first()
            
            if existing_tx:
                continue
            
            # Determine cost based on execution type
            if ex.execution_type == "ticker":
                cost = COST_PER_ANALYSIS
                tx_type = "analysis_cost"
                description = f"Backfilled: Analysis for {ex.subject_id}"
                analysis_count += 1
            elif ex.execution_type == "daily_digest":
                cost = COST_PER_DIGEST
                tx_type = "digest_cost"
                description = f"Backfilled: Digest for {ex.subject_id}"
                digest_count += 1
            else:
                # Unknown execution type, skip
                continue
            
            # Get user's current balance (approximation)
            user = db.query(User).filter(User.id == ex.creator_id).first()
            if not user:
                continue
            
            # Create transaction
            metadata = {
                "execution_id": ex.id,
                "subject_id": ex.subject_id,
                "backfilled": True
            }
            
            tx = TokenTransaction(
                user_id=ex.creator_id,
                amount=-cost,
                balance_after=user.token_balance,  # Current balance (not historically accurate)
                transaction_type=tx_type,
                related_entity_type="execution",
                related_entity_id=ex.id,
                metadata_json=json.dumps(metadata),
                description=description,
                created_at=ex.created_at,
            )
            db.add(tx)
            
            # Commit in batches to avoid memory issues
            if (analysis_count + digest_count) % 100 == 0:
                db.commit()
        
        db.commit()
        print(f"✓ Created {analysis_count} analysis cost transactions")
        print(f"✓ Created {digest_count} digest cost transactions")
        
        # 3. Summary
        print("\n" + "=" * 60)
        print("✅ Backfill completed successfully!")
        print("\nSummary:")
        print(f"- Initial balances: {initial_count}")
        print(f"- Analysis costs: {analysis_count}")
        print(f"- Digest costs: {digest_count}")
        print(f"- Total transactions created: {initial_count + analysis_count + digest_count}")
        
        total_tx = db.query(TokenTransaction).count()
        print(f"\nTotal transactions in database: {total_tx}")
        
        print("\n⚠️  Note: Historical balance_after values are approximations.")
        print("   They reflect current balances, not actual historical balances.")
        
    except Exception as e:
        print(f"\n❌ Backfill failed: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        backfill_transactions()
    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user.")
        sys.exit(1)

# Made with Bob

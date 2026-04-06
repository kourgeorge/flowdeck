#!/usr/bin/env python3
"""
Check token transactions after reset
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.db_models import Usage, User
from sqlalchemy import func

def main():
    db = SessionLocal()
    try:
        # Get transaction count
        tx_count = db.query(func.count(Usage.id)).scalar()
        print(f'Total transactions: {tx_count}')
        print()
        
        # Get transactions by type
        print('Transactions by type:')
        type_counts = db.query(
            Usage.transaction_type,
            func.count(Usage.id)
        ).group_by(Usage.transaction_type).all()
        for tx_type, count in type_counts:
            print(f'  {tx_type}: {count}')
        print()
        
        # Get user balances
        print('User balances:')
        users = db.query(User).all()
        for user in users:
            balance = db.query(func.sum(Usage.amount)).filter(
                Usage.user_id == user.id
            ).scalar() or 0
            print(f'  User {user.id} ({user.email}): {balance} tokens')
        print()
        
        # Show recent transactions
        print('Recent transactions (last 10):')
        recent = db.query(Usage).order_by(Usage.created_at.desc()).limit(10).all()
        for tx in recent:
            print(f'  {tx.created_at} | User {tx.user_id} | {tx.transaction_type} | {tx.amount:+d} | {tx.description}')
            
    finally:
        db.close()

if __name__ == '__main__':
    main()

# Made with Bob

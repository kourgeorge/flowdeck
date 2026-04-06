#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.db_models import Usage
from sqlalchemy import func

db = SessionLocal()
user_id = 13

total = db.query(func.sum(Usage.amount)).filter(Usage.user_id == user_id).scalar()
print(f'Sum of all transactions: {total}')

recent = db.query(Usage).filter(Usage.user_id == user_id).order_by(Usage.created_at.desc()).limit(5).all()
print('\nLast 5 transactions:')
for tx in recent:
    print(f'  {tx.transaction_type}: {tx.amount:+d} (balance_after: {tx.balance_after}) - {tx.description}')

db.close()

# Made with Bob

#!/usr/bin/env python3
"""
Reset all user token balances to 1000.
Clears all existing transactions and creates fresh initial balance transactions.

WARNING: This will delete ALL token transaction history!

Run from repo root: python backend/scripts/reset_all_balances.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.db_models import User, Usage

INITIAL_BALANCE = 1000


def reset_all_balances():
    """Reset all user balances to 1000 tokens."""
    print("=" * 70)
    print("RESETTING ALL USER TOKEN BALANCES TO 1000")
    print("=" * 70)
    print("\nWARNING: This will delete ALL token transaction history!")
    print("Press Ctrl+C to cancel, or Enter to continue...")
    input()
    
    db = SessionLocal()
    try:
        # Get all users
        users = db.query(User).all()
        print(f"\nFound {len(users)} users")
        
        # Delete all existing transactions
        print("\n1. Deleting all existing usage transactions...")
        deleted_count = db.query(Usage).delete()
        print(f"   ✓ Deleted {deleted_count} transactions")
        
        # Create fresh initial balance transactions for all users
        print("\n2. Creating fresh initial balance transactions...")
        for user in users:
            # Update User.token_balance column (for backward compatibility)
            user.token_balance = INITIAL_BALANCE
            
            # Create initial balance transaction
            tx = Usage(
                user_id=user.id,
                amount=INITIAL_BALANCE,
                balance_after=INITIAL_BALANCE,
                transaction_type="initial_balance",
                description="Initial token balance (reset)",
                created_at=datetime.now(timezone.utc)
            )
            db.add(tx)
            print(f"   ✓ Reset {user.email} to {INITIAL_BALANCE} tokens")
        
        # Commit all changes
        db.commit()
        
        print("\n" + "=" * 70)
        print(f"✅ Successfully reset {len(users)} user balances to {INITIAL_BALANCE} tokens")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        db.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        reset_all_balances()
    except Exception as e:
        print(f"\n❌ Reset failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob

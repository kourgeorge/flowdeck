#!/usr/bin/env python3
"""
Verify token balances match transaction history for all users.
Run from repo root: python backend/scripts/verify_token_balances.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models.db_models import User, TokenTransaction
from services.token_service import INITIAL_BALANCE


def verify_all_balances():
    """Verify all user balances match their transaction history."""
    
    print("Verifying token balances...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        users = db.query(User).all()
        total_users = len(users)
        valid_count = 0
        invalid_count = 0
        issues = []
        
        for user in users:
            # Get all transactions for this user
            transactions = db.query(TokenTransaction).filter(
                TokenTransaction.user_id == user.id
            ).order_by(TokenTransaction.created_at).all()
            
            if not transactions:
                # No transactions yet - should have initial balance or 0
                expected = user.token_balance  # Accept current balance
                if user.token_balance == expected:
                    valid_count += 1
                else:
                    invalid_count += 1
                    issues.append({
                        'user_id': user.id,
                        'email': user.email,
                        'current': user.token_balance,
                        'expected': expected,
                        'issue': 'No transactions but unexpected balance'
                    })
                continue
            
            # Calculate expected balance from transactions
            calculated_balance = sum(tx.amount for tx in transactions)
            
            # Check last transaction's balance_after
            last_tx = transactions[-1]
            
            # Verify consistency
            is_valid = True
            issue_desc = []
            
            if calculated_balance != user.token_balance:
                is_valid = False
                issue_desc.append(f"Sum of transactions ({calculated_balance}) != current balance ({user.token_balance})")
            
            if last_tx.balance_after != user.token_balance:
                is_valid = False
                issue_desc.append(f"Last tx balance_after ({last_tx.balance_after}) != current balance ({user.token_balance})")
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                issues.append({
                    'user_id': user.id,
                    'email': user.email,
                    'current': user.token_balance,
                    'calculated': calculated_balance,
                    'last_tx_balance': last_tx.balance_after,
                    'tx_count': len(transactions),
                    'issues': '; '.join(issue_desc)
                })
        
        # Print results
        print(f"\nTotal users: {total_users}")
        print(f"✓ Valid balances: {valid_count}")
        print(f"✗ Invalid balances: {invalid_count}")
        
        if issues:
            print("\n" + "=" * 60)
            print("ISSUES FOUND:")
            print("=" * 60)
            for issue in issues:
                print(f"\nUser ID: {issue['user_id']} ({issue['email']})")
                print(f"  Current balance: {issue['current']}")
                if 'calculated' in issue:
                    print(f"  Calculated from transactions: {issue['calculated']}")
                    print(f"  Last transaction balance_after: {issue['last_tx_balance']}")
                    print(f"  Transaction count: {issue['tx_count']}")
                print(f"  Issues: {issue.get('issues', issue.get('issue', 'Unknown'))}")
        
        print("\n" + "=" * 60)
        if invalid_count == 0:
            print("✅ All balances verified successfully!")
        else:
            print(f"⚠️  Found {invalid_count} balance discrepancies")
            print("   Review the issues above and investigate.")
        
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        verify_all_balances()
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
        sys.exit(1)

# Made with Bob

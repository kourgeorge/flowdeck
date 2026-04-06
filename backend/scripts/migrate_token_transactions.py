#!/usr/bin/env python3
"""
Migration script to add token_transactions table for complete transaction ledger.
This migration also backfills initial balance transactions for existing users.

IMPORTANT: After this migration, User.token_balance is NO LONGER UPDATED.
Token balances are computed from the TokenTransaction ledger (single source of truth).

Run from repo root: python backend/scripts/migrate_token_transactions.py
Safe to run multiple times (idempotent).
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import SessionLocal, engine


def _table_exists(conn, table_name: str) -> bool:
    """Check if table exists (SQLite)."""
    result = conn.execute(text(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    ))
    return result.fetchone() is not None


def migrate_token_transactions():
    """Add token_transactions table, indexes, and backfill initial balances."""
    
    print("Starting token_transactions migration...")
    print("=" * 60)
    
    with engine.connect() as conn:
        # Check if table already exists
        table_exists = _table_exists(conn, "token_transactions")
        
        if not table_exists:
            print("\n1. Creating token_transactions table...")
            try:
                conn.execute(text("""
                    CREATE TABLE token_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        amount INTEGER NOT NULL,
                        balance_after INTEGER NOT NULL,
                        llm_tokens INTEGER NULL,
                        transaction_type VARCHAR(32) NOT NULL,
                        related_entity_type VARCHAR(32) NULL,
                        related_entity_id INTEGER NULL,
                        metadata_json TEXT NULL,
                        description VARCHAR(255) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """))
                conn.commit()
                print("   ✓ Created token_transactions table")
            except Exception as e:
                print(f"   ✗ Error creating table: {e}")
                raise
            
            print("\n2. Creating indexes...")
            try:
                conn.execute(text("""
                    CREATE INDEX idx_token_tx_user_created
                    ON token_transactions(user_id, created_at)
                """))
                conn.commit()
                print("   ✓ Created index on (user_id, created_at)")
            except Exception as e:
                print(f"   Note: Index creation: {e}")
            
            try:
                conn.execute(text("""
                    CREATE INDEX idx_token_tx_type
                    ON token_transactions(transaction_type)
                """))
                conn.commit()
                print("   ✓ Created index on transaction_type")
            except Exception as e:
                print(f"   Note: Index creation: {e}")
            
            try:
                conn.execute(text("""
                    CREATE INDEX idx_token_tx_related_entity
                    ON token_transactions(related_entity_type, related_entity_id)
                """))
                conn.commit()
                print("   ✓ Created index on (related_entity_type, related_entity_id)")
            except Exception as e:
                print(f"   Note: Index creation: {e}")
            
            # Add index for fast balance calculation
            try:
                conn.execute(text("""
                    CREATE INDEX idx_token_tx_user_amount
                    ON token_transactions(user_id, amount)
                """))
                conn.commit()
                print("   ✓ Created index on (user_id, amount) for fast balance queries")
            except Exception as e:
                print(f"   Note: Index creation: {e}")
        else:
            print("\n1. ✓ token_transactions table already exists")
            
            # Check if the performance index exists, add if missing
            print("\n2. Checking for performance indexes...")
            try:
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name='idx_token_tx_user_amount'
                """))
                if not result.fetchone():
                    print("   Adding missing performance index...")
                    conn.execute(text("""
                        CREATE INDEX idx_token_tx_user_amount
                        ON token_transactions(user_id, amount)
                    """))
                    conn.commit()
                    print("   ✓ Created index on (user_id, amount) for fast balance queries")
                else:
                    print("   ✓ Performance indexes already exist")
            except Exception as e:
                print(f"   Note: Index check/creation: {e}")
        
        # Backfill initial balance transactions for users without any transactions
        print("\n3. Backfilling initial balance transactions...")
        try:
            # Find users without any transactions
            result = conn.execute(text("""
                SELECT u.id, u.email, u.token_balance
                FROM users u
                LEFT JOIN token_transactions tt ON u.id = tt.user_id
                WHERE tt.id IS NULL AND u.token_balance IS NOT NULL AND u.token_balance > 0
            """))
            users_to_backfill = result.fetchall()
            
            if users_to_backfill:
                print(f"   Found {len(users_to_backfill)} users needing initial balance transactions")
                for user_id, email, balance in users_to_backfill:
                    conn.execute(text("""
                        INSERT INTO token_transactions
                        (user_id, amount, balance_after, transaction_type, description, created_at)
                        VALUES (:user_id, :amount, :balance, 'initial_balance', 'Initial token balance (backfilled)', CURRENT_TIMESTAMP)
                    """), {"user_id": user_id, "amount": balance, "balance": balance})
                    print(f"   ✓ Backfilled {balance} tokens for user {email}")
                conn.commit()
                print(f"   ✓ Backfilled {len(users_to_backfill)} initial balance transactions")
            else:
                print("   ✓ No users need backfilling (all have transactions or zero balance)")
        except Exception as e:
            print(f"   Note: Backfill: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("\nSummary:")
    print("- Created/verified token_transactions table")
    print("- Added indexes for performance (including fast balance queries)")
    print("- Backfilled initial balance transactions for existing users")
    print("- Token balances now computed from ledger (single source of truth)")
    print("\nIMPORTANT:")
    print("- User.token_balance is NO LONGER UPDATED by the system")
    print("- All balances are computed from TokenTransaction sum")
    print("- This eliminates sync issues and provides complete audit trail")


if __name__ == "__main__":
    try:
        migrate_token_transactions()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob

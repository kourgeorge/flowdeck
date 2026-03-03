"""
Migration script to create the api_keys table.

Run this script to add API key support to an existing FlowDeck database.
"""

from sqlalchemy import create_engine, text
from pathlib import Path
import sys
import os

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import DATABASE_URL

def migrate():
    """Create the api_keys table."""
    engine = create_engine(DATABASE_URL)
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        key_hash VARCHAR(255) NOT NULL UNIQUE,
        key_prefix VARCHAR(16) NOT NULL,
        name VARCHAR(255) NOT NULL,
        last_used_at DATETIME,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """
    
    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);",
    ]
    
    with engine.connect() as conn:
        print("Creating api_keys table...")
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✓ api_keys table created")
        
        for idx_sql in create_indexes_sql:
            print(f"Creating index...")
            conn.execute(text(idx_sql))
            conn.commit()
        print("✓ Indexes created")
    
    print("\n✅ Migration complete! API key support is now enabled.")
    print("Users can now create API keys via POST /api/api-keys")

if __name__ == "__main__":
    migrate()

# Made with Bob

import sqlite3
from pathlib import Path
import sys

# Add project root to path for core imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_connection

def migrate():
    print("--- MIGRATION v0.8: ASSET REVIEW COLUMNS ---")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if review_status exists
    cursor.execute("PRAGMA table_info(asset_briefs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "review_status" not in columns:
        print("  [DB] Adding review_status to asset_briefs...")
        cursor.execute("ALTER TABLE asset_briefs ADD COLUMN review_status TEXT DEFAULT 'pending'")
    else:
        print("  [DB] review_status already exists.")
        
    if "review_reason" not in columns:
        print("  [DB] Adding review_reason to asset_briefs...")
        cursor.execute("ALTER TABLE asset_briefs ADD COLUMN review_reason TEXT")
    else:
        print("  [DB] review_reason already exists.")
        
    if "review_confidence" not in columns:
        print("  [DB] Adding review_confidence to asset_briefs...")
        cursor.execute("ALTER TABLE asset_briefs ADD COLUMN review_confidence REAL")
    else:
        print("  [DB] review_confidence already exists.")
        
    conn.commit()
    conn.close()
    print("✓ Migration v0.8 complete.")

if __name__ == "__main__":
    migrate()

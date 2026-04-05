import sqlite3
from pathlib import Path
import sys

# Resolve path to core/db.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_connection

def migrate():
    print("="*60)
    print("Migration v0.6: Adding Reference Image Columns")
    print("="*60)
    
    conn = get_connection()
    try:
        # 1. reference_image_path
        cursor = conn.execute("SELECT COUNT(*) FROM pragma_table_info('game_clip_index') WHERE name='reference_image_path'")
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            print("  > Adding column: reference_image_path")
            conn.execute("ALTER TABLE game_clip_index ADD COLUMN reference_image_path TEXT NULL")
        else:
            print("  - Column 'reference_image_path' already exists. Skipping.")
            
        # 2. needs_reference
        cursor = conn.execute("SELECT COUNT(*) FROM pragma_table_info('game_clip_index') WHERE name='needs_reference'")
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            print("  > Adding column: needs_reference")
            conn.execute("ALTER TABLE game_clip_index ADD COLUMN needs_reference INTEGER DEFAULT 0")
        else:
            print("  - Column 'needs_reference' already exists. Skipping.")
            
        conn.commit()
        print("\nMigration Complete.")
        
    except Exception as e:
        print(f"\nMigration FAILED: {e}")
        conn.rollback()
    finally:
        conn.close()
    print("="*60)

if __name__ == "__main__":
    migrate()

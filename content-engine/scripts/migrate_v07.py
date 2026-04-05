import sqlite3
from pathlib import Path
import sys

# Ensure root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.db import get_connection

def migrate():
    print("--- Database Migration v0.7: Style Notes ---")
    conn = get_connection()
    try:
        # 1. Add style_notes to game_clip_index
        cursor = conn.execute("PRAGMA table_info('game_clip_index')")
        cols = [row[1] for row in cursor.fetchall()]
        if "style_notes" not in cols:
            print("  - Adding style_notes to game_clip_index...")
            conn.execute("ALTER TABLE game_clip_index ADD COLUMN style_notes TEXT")
        else:
            print("  ✓ style_notes already exists in game_clip_index")
            
        # 2. Add optimized_prompt to asset_briefs for debugging
        cursor = conn.execute("PRAGMA table_info('asset_briefs')")
        cols = [row[1] for row in cursor.fetchall()]
        if "optimized_prompt" not in cols:
            print("  - Adding optimized_prompt to asset_briefs...")
            conn.execute("ALTER TABLE asset_briefs ADD COLUMN optimized_prompt TEXT")
        else:
            print("  ✓ optimized_prompt already exists in asset_briefs")

        conn.commit()
        print("✓ Migration successful.")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

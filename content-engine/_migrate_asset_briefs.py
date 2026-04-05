import sqlite3
from pathlib import Path

DB_PATH = Path("database/content_engine.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE asset_briefs ADD COLUMN drawtext_string TEXT")
        print("✓ Added drawtext_string to asset_briefs")
    except sqlite3.OperationalError:
        print("  Column drawtext_string already exists")
        
    try:
        conn.execute("ALTER TABLE asset_briefs ADD COLUMN key_phrase TEXT")
        print("✓ Added key_phrase to asset_briefs")
    except sqlite3.OperationalError:
        print("  Column key_phrase already exists")
        
    try:
        conn.execute("ALTER TABLE asset_briefs ADD COLUMN pollinations_prompt TEXT")
        print("✓ Added pollinations_prompt to asset_briefs")
    except sqlite3.OperationalError:
        print("  Column pollinations_prompt already exists")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()

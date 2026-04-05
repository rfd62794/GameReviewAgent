import sqlite3
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.index_manager import IndexManager

DB_PATH = Path("database/content_engine.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS game_clip_index (
            id INTEGER PRIMARY KEY,
            game_title TEXT NOT NULL,
            mechanic TEXT NOT NULL,
            search_query TEXT NOT NULL,
            channel TEXT NULL,
            times_successful INTEGER DEFAULT 0,
            times_attempted INTEGER DEFAULT 0,
            confidence_avg REAL DEFAULT 0.0,
            verified INTEGER DEFAULT 0,
            suggested_by TEXT DEFAULT 'llm',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            last_used_at TEXT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_game_mechanic 
        ON game_clip_index(game_title, mechanic);
        """)
        
        # Seed Data
        conn.executescript("""
        INSERT INTO game_clip_index 
        (game_title, mechanic, search_query, verified, suggested_by)
        VALUES
        ('Cookie Clicker', 'prestige_reset', 
         'Cookie Clicker ascension gameplay', 1, 'director'),
        ('Cookie Clicker', 'prestige_reset',
         'Cookie Clicker heavenly chips guide', 1, 'director'),
        ('Adventure Capitalist', 'prestige_reset',
         'Adventure Capitalist angel investors reset gameplay', 
         1, 'director');
        """)
        print("Migration and seed successful.")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.commit()
        conn.close()

if __name__ == "__main__":
    migrate()

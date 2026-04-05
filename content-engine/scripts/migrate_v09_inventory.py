import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import get_connection

def migrate():
    print("="*70)
    print("ContentEngine Migration v0.9 — Asset Inventory System")
    print("="*70)

    conn = get_connection()
    
    # 1. Create asset_inventory table
    print("[1/2] Creating asset_inventory table...")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS asset_inventory (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        
        -- Asset identity
        asset_path      TEXT NOT NULL UNIQUE,
        asset_type      TEXT NOT NULL,  -- clip | still | ai_image | wiki_screenshot
        file_size_kb    INTEGER,
        duration_s      REAL,      -- clips only
        width           INTEGER,
        height          INTEGER,
        
        -- Source tracking
        source          TEXT NOT NULL,      -- youtube | wiki | local | ai_generated
        source_url      TEXT,      -- YouTube URL, wiki URL
        source_query    TEXT,      -- query that found it
        youtube_video_id TEXT,
        youtube_channel TEXT,
        
        -- Game and mechanic descriptors
        game_title      TEXT,
        mechanic        TEXT,
        moment          TEXT,      -- what is on screen
        tags            TEXT,      -- JSON array of keywords
        
        -- Quality metadata
        review_status   TEXT DEFAULT 'pending' 
                        CHECK (review_status IN ('pending', 'accepted', 'rejected')),
        review_confidence REAL,
        review_reason   TEXT,
        times_used      INTEGER DEFAULT 0,
        last_used_at    TEXT,
        
        -- Reuse matching
        segment_text_sample TEXT,  -- first 100 chars of segment that sourced it
        visual_description  TEXT,   -- LLM-generated description
        
        created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        updated_at      TEXT
    )
    """)
    
    # 2. Create Indexes
    print("[2/2] Creating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inventory_game_mechanic ON asset_inventory(game_title, mechanic)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inventory_type_status ON asset_inventory(asset_type, review_status)")
    
    # 3. Create clip_download_queue table
    print("[3/3] Creating clip_download_queue table...")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS clip_download_queue (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        youtube_url     TEXT NOT NULL,
        youtube_video_id TEXT NOT NULL,
        timestamp_start INTEGER NOT NULL,
        timestamp_end   INTEGER NOT NULL,
        confidence      REAL NOT NULL,
        mechanic_shown  TEXT NOT NULL,
        game_title      TEXT,
        status          TEXT DEFAULT 'queued'
                        CHECK (status IN ('queued', 'downloading', 'done', 'failed')),
        created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
        processed_at    TEXT
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_conf ON clip_download_queue(status, confidence)")
    
    conn.commit()
    conn.close()
    
    print()
    print("✓ Migration complete. Schema v0.9 ready.")
    print("="*70)

if __name__ == "__main__":
    migrate()

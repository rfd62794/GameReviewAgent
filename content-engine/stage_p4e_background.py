import argparse
import logging
import sqlite3
import time
from pathlib import Path
from datetime import datetime

from core.db import get_connection
from core.youtube_sourcer import download_clip
from core.asset_reviewer import evaluate_asset, generate_visual_description
from core.inventory_manager import add_asset

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def process_queue():
    """
    Process the clip download queue for background inventory enrichment.
    Runs asynchronously/after-hours to extract maximum value from identified videos.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    print("="*70)
    print("ContentEngine Stage P4e — Background Inventory Harvesting")
    print("="*70)
    
    # 1. Fetch queued segments ordered by confidence
    # We process 'queued' status only.
    rows = conn.execute("""
        SELECT * FROM clip_download_queue 
        WHERE status = 'queued'
        ORDER BY confidence DESC
    """).fetchall()
    
    if not rows:
        print("  Queue is empty. No harvesting tasks.")
        conn.close()
        return

    print(f"  Found {len(rows)} segments in queue. Starting harvest...")

    for row in rows:
        url = row["youtube_url"]
        start = row["timestamp_start"]
        end = row["timestamp_end"]
        mechanic = row["mechanic_shown"]
        game = row["game_title"]
        row_id = row["id"]
        
        print(f"\n  [Harvest] Processing: {game or 'Unknown'} | {mechanic} at {start}s...")
        
        # Update status to downloading
        conn.execute("UPDATE clip_download_queue SET status = 'downloading' WHERE id = ?", (row_id,))
        conn.commit()
        
        # a) Download Clip
        clip_path = download_clip(url, start, end)
        if not clip_path:
            print(f"    ✗ Download failed for {url}")
            conn.execute("UPDATE clip_download_queue SET status = 'failed' WHERE id = ?", (row_id,))
            conn.commit()
            continue
            
        print(f"    ✓ Downloaded: {clip_path.name}")
        
        # b) Evaluate/Review
        # We need to construct a minimal segment dict for the reviewer
        dummy_seg = {
            "id": f"harvest_{row_id}",
            "segment_index": 0,
            "game_title": game,
            "mechanic": mechanic,
            "moment": f"Background harvest: {mechanic}",
            "selected_asset": str(clip_path),
            "asset_source": "youtube",
            "segment_text": f"This is an automated background harvest of {mechanic} gameplay."
        }
        
        review = evaluate_asset(dummy_seg)
        decision = review.get("decision", "REPLACE")
        print(f"    [Review] Decision: {decision} (Conf: {review.get('confidence', 0):.2f})")
        
        # c) Index/Fail
        if decision == "ACCEPT":
            # Generate visual description
            print(f"    [Inventory] Indexing visual description... ", end="", flush=True)
            visual_desc = generate_visual_description(str(clip_path))
            print("DONE.")
            
            # Add to inventory
            success = add_asset(dummy_seg, review, visual_description=visual_desc)
            if success:
                print("    ✓ Successfully added to Asset Inventory.")
                conn.execute(
                    "UPDATE clip_download_queue SET status = 'done', processed_at = ? WHERE id = ?",
                    (datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'), row_id)
                )
            else:
                print("    ✗ Failed to add to inventory (DB error).")
                conn.execute("UPDATE clip_download_queue SET status = 'failed' WHERE id = ?", (row_id,))
        else:
            print(f"    ✗ Rejected by reviewer: {review.get('reason', 'No reason')}")
            conn.execute("UPDATE clip_download_queue SET status = 'failed', processed_at = ? WHERE id = ?", 
                         (datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'), row_id))
        
        conn.commit()
        
    conn.close()
    print("\n" + "="*70)
    print("Harvest complete.")

if __name__ == "__main__":
    process_queue()

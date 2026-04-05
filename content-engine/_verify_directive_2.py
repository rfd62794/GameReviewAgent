import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.reference_manager import get_reference
from core.db import get_connection

def verify_live():
    print("\n--- LIVE REFERENCE TEST: Cookie Clicker ---")
    game = "Cookie Clicker"
    
    # 1. Clear existing for clean test (optional, but good for first run)
    # conn = get_connection()
    # conn.execute("UPDATE game_clip_index SET reference_image_path = NULL WHERE game_title = ?", (game,))
    # conn.commit()
    # conn.close()
    
    # 2. Acquire
    ref_bytes = get_reference(game)
    
    if ref_bytes:
        print(f"SUCCESS: Reference acquired for {game}")
        print(f"File Size: {len(ref_bytes) / 1024:.2f} KB")
        
        # 3. Check DB
        conn = get_connection()
        row = conn.execute("SELECT reference_image_path FROM game_clip_index WHERE game_title = ?", (game,)).fetchone()
        if row:
            print(f"DB Path: {row['reference_image_path']}")
        conn.close()
    else:
        print(f"FAILED: No reference acquired for {game}")
    print("------------------------------------------\n")

if __name__ == "__main__":
    verify_live()

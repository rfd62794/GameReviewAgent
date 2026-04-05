"""
ContentEngine P4 — Mechanic Extraction Stage

Authoritative extraction of game title, mechanics, and visual moments 
from segment text using the LLM mechanic_extractor.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection
from core.mechanic_extractor import extract as extract_mechanic

SCRIPT_ID = 1

def main():
    print("=" * 70)
    print("ContentEngine P4 — Mechanic Extraction")
    print("=" * 70)
    print()

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    # "Pending" = mechanic IS NULL AND matches our current script
    cursor = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = ? AND mechanic IS NULL ORDER BY segment_index",
        (SCRIPT_ID,)
    )
    segments = cursor.fetchall()
    
    if not segments:
        print(f"✓ No pending segments for Script ID {SCRIPT_ID} (already extracted or none found).")
        conn.close()
        return

    print(f"[1/2] Extracting metadata for {len(segments)} segments...")

    for seg in segments:
        print(f"  > seg {seg['segment_index']}: ", end="", flush=True)
        
        # Call core module
        extracted = extract_mechanic(seg["segment_text"])
        
        # Parse results
        games      = extracted.get("games", [])
        mechanic   = extracted.get("mechanic") or "unknown"
        moment     = extracted.get("moment") or "gameplay"
        queries    = extracted.get("search_queries", [])
        game_title = games[0] if games else None
        
        print(f"game={game_title!r} mechanic={mechanic!r}")

        # Update DB
        conn.execute(
            """
            UPDATE asset_briefs 
            SET game_title = ?, 
                mechanic = ?, 
                moment = ?, 
                search_query = ?
            WHERE id = ?
            """,
            (game_title, mechanic, moment, json.dumps(queries), seg["id"])
        )
        conn.commit()

    conn.close()
    print()
    print("[2/2] Extraction Complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()

"""
ContentEngine P4 & P4b — Asset Sourcing & Selection

Reads pending segments from `asset_briefs`, delegates to `asset_sourcer`,
and updates the database with the selected asset path.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection
from core.asset_sourcer import source_asset_for_segment

SCRIPT_ID = 1  # Will be mapped dynamically later but matches our test flow.

def main():
    print("=" * 70)
    print("ContentEngine P4 — Asset Sourcing")
    print("=" * 70)
    print()

    conn = get_connection()
    conn.row_factory = dict # Ensure we can fetch as dict easily
    cursor = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = ? AND status = 'pending' ORDER BY segment_index",
        (SCRIPT_ID,)
    )
    segments = cursor.fetchall()
    
    if not segments:
        print(f"✗ No pending segments found for Script ID {SCRIPT_ID}.")
        sys.exit(1)

    print(f"[1/2] Sourcing assets for {len(segments)} segments...")

    for seg in segments:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"  > Seg {seg['segment_index']} ({label}) - {seg['visual_type']}")
        
        result = source_asset_for_segment(seg)
        
        if result["path"]:
            print(f"    ✓ Sourced [{result['source']}]: {Path(result['path']).name}")
            conn.execute(
                "UPDATE asset_briefs SET selected_asset = ?, asset_source = ?, status = 'sourced' WHERE id = ?",
                (result["path"], result["source"], seg["id"])
            )
        else:
            print("    ✗ FAILED to source asset.")

    conn.commit()
    conn.close()

    print()
    print("[2/2] Asset Sourcing Complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()

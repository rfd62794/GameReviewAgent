"""
ContentEngine P3b — Transcript Segmentation

Reads approved script from the database, segments the body into paragraphs,
assigns visual metadata heuristics, and writes to `asset_briefs`.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection
from core.segmentation import segment_script

SCRIPT_ID = 2

def main():
    print("=" * 70)
    print("ContentEngine P3b — Transcript Segmentation")
    print("=" * 70)
    print()

    conn = get_connection()
    row = conn.execute(
        "SELECT id, hook_short_script, mid_form_body, tags "
        "FROM scripts WHERE id = ?",
        (SCRIPT_ID,)
    ).fetchone()

    if not row:
        print(f"✗ Script ID {SCRIPT_ID} not found.")
        sys.exit(1)

    print(f"[1/3] Loaded script {SCRIPT_ID}")
    
    tags = []
    try:
        tags = json.loads(row["tags"])
    except:
        pass

    print("[2/3] Segmenting and annotating text...")
    segments = segment_script(
        script_id=row["id"],
        hook_text=row["hook_short_script"],
        body_text=row["mid_form_body"],
        tags=tags
    )

    print(f"      Created {len(segments)} segments. Inserting to database...")
    
    # Clear existing briefs for this script to allow safe re-runs
    conn.execute("DELETE FROM asset_briefs WHERE script_id = ?", (SCRIPT_ID,))

    for seg in segments:
        conn.execute(
            """
            INSERT INTO asset_briefs 
            (script_id, segment_index, segment_text, estimated_duration_s, visual_type, search_query, ai_image_prompt, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                seg["script_id"],
                seg["segment_index"],
                seg["segment_text"],
                seg["estimated_duration_s"],
                seg["visual_type"],
                seg["search_query"],
                seg["ai_image_prompt"]
            )
        )
    
    conn.commit()
    conn.close()

    print("[3/3] Segmentation Complete.")
    print("-" * 70)
    for seg in segments:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"Seg {seg['segment_index']} [{label}] - {seg['estimated_duration_s']}s")
        print(f"  Type:  {seg['visual_type']}")
        if seg["visual_type"] == "ai_image":
            print(f"  Prompt: {seg['ai_image_prompt']}")
        else:
            print(f"  Query:  {seg['search_query']}")
        print()
    print("=" * 70)

if __name__ == "__main__":
    main()

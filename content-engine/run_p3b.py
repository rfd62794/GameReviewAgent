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
from core.mechanic_extractor import extract as extract_mechanic

SCRIPT_ID = 1

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

    print(f"      Created {len(segments)} segments. Running mechanic extractor + inserting...")
    
    # Clear existing briefs for this script to allow safe re-runs
    conn.execute("DELETE FROM asset_briefs WHERE script_id = ?", (SCRIPT_ID,))

    for seg in segments:
        # Run mechanic extractor on each segment to get authoritative game/mechanic/moment
        extracted = extract_mechanic(seg["segment_text"])
        games   = extracted.get("games", [])
        mechanic = extracted.get("mechanic") or None
        moment   = extracted.get("moment") or None
        game_title = games[0] if games else None

        print(f"    seg {seg['segment_index']}: game={game_title!r} mechanic={mechanic!r} moment={moment!r}")

        conn.execute(
            """
            INSERT INTO asset_briefs 
            (script_id, segment_index, segment_text, estimated_duration_s,
             visual_type, search_query, ai_image_prompt,
             game_title, mechanic, moment, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                seg["script_id"],
                seg["segment_index"],
                seg["segment_text"],
                seg["estimated_duration_s"],
                seg["visual_type"],
                seg["search_query"],
                seg["ai_image_prompt"],
                game_title,
                mechanic,
                moment,
            )
        )
    
    conn.commit()
    conn.close()

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    final_segs = conn.execute("SELECT * FROM asset_briefs WHERE script_id = ? ORDER BY segment_index", (SCRIPT_ID,)).fetchall()
    conn.close()

    print("[3/3] Segmentation Complete.")
    print("-" * 70)
    for seg in final_segs:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"Seg {seg['segment_index']} [{label}] - {seg['estimated_duration_s']}s")
        print(f"  Type:     {seg['visual_type']}")
        print(f"  Game:     {seg['game_title']!r}")
        print(f"  Mechanic: {seg['mechanic']!r}")
        print(f"  Moment:   {seg['moment']!r}")
        if seg["ai_image_prompt"]:
            print(f"  AI Prompt: {seg['ai_image_prompt']}")
        else:
            print(f"  Search:    {seg['search_query']}")
        print()
    print("=" * 70)

if __name__ == "__main__":
    main()

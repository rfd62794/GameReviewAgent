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
from core.prompt_builder import (
    extract_key_phrase,
    build_drawtext_string,
    build_pollinations_prompt,
    build_infographic_prompt
)

SCRIPT_ID = 1  # Will be mapped dynamically later but matches our test flow.

def main():
    print("=" * 70)
    print("ContentEngine P4b — Asset Sourcing & Prompt Building")
    print("=" * 70)
    print()

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = ? AND status = 'pending' ORDER BY segment_index",
        (SCRIPT_ID,)
    )
    segments = cursor.fetchall()
    
    if not segments:
        print(f"✗ No pending segments found for Script ID {SCRIPT_ID}.")
        sys.exit(1)

    print(f"[1/2] Sourcing assets and building prompts for {len(segments)} segments...")

    for seg in segments:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"  > Seg {seg['segment_index']} ({label})")
        
        # 1. Source Asset
        result = source_asset_for_segment(seg)
        
        # 2. Build Prompts & Overlays
        key_phrase = extract_key_phrase(seg["segment_text"])
        drawtext_filter = build_drawtext_string(key_phrase)
        
        # Pollinations prompt (could be game-based or infographic)
        if seg.get("ai_image_prompt"):
            # If segmentation already suggested an infographic/abstract prompt, use it
            poll_prompt = seg["ai_image_prompt"]
        else:
            # Build from mechanic extractor columns (game, mechanic, moment)
            poll_prompt = build_pollinations_prompt(
                seg.get("game_title"), 
                seg.get("mechanic"), 
                seg.get("moment")
            )
            
        # 3. Update Database
        if result["path"]:
            # If we found an AI image, ensure visual_type is 'ai_image'
            # (In MVP, everything is ai_image or gameplay_clip)
            new_vtype = seg["visual_type"]
            if result["source"] == "ai_generated":
                new_vtype = "ai_image"
                
            print(f"    ✓ Sourced [{result['source']}]: {Path(result['path']).name}")
            print(f"    ✓ Prompt: {key_phrase}")
            
            conn.execute(
                """
                UPDATE asset_briefs 
                SET selected_asset = ?, 
                    asset_source = ?, 
                    visual_type = ?,
                    drawtext_string = ?,
                    key_phrase = ?,
                    pollinations_prompt = ?,
                    status = 'sourced' 
                WHERE id = ?
                """,
                (
                    result["path"], 
                    result["source"], 
                    new_vtype,
                    drawtext_filter,
                    key_phrase,
                    poll_prompt,
                    seg["id"]
                )
            )
            conn.commit()
        else:
            print("    ✗ FAILED to source asset.")

    conn.close()

    print()
    print("[2/2] Asset Sourcing & Prompt Building Complete.")
    print("=" * 70)

if __name__ == "__main__":
    main()

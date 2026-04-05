import os
import sys
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection
from core.mechanic_extractor import extract as extract_mechanic
from core.asset_sourcer import source_asset_for_segment
from core.asset_reviewer import evaluate_asset

# Config
SCRIPT_ID = 1
REPLACE_INDICES = [0, 2, 12]

def main():
    print("\n" + "="*80)
    print("ContentEngine P4d — Targeted Re-sourcing Pass (REFINED)")
    print("="*80)

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    # 1. Reset the target segments to trigger re-extraction and re-sourcing
    print(f"  [P4d] Resetting segments {REPLACE_INDICES} for re-processing...")
    conn.execute(
        f"UPDATE asset_briefs SET mechanic = NULL, search_query = '[]', status = 'pending', selected_asset = NULL, asset_source = NULL WHERE script_id = ? AND segment_index IN ({','.join(map(str, REPLACE_INDICES))})",
        (SCRIPT_ID,)
    )
    conn.commit()

    # 2. Re-Extract with New Softened Queries
    print(f"  [P4d] Step 1: Re-extracting with Softened Query Prompt...")
    segments = conn.execute(
        f"SELECT * FROM asset_briefs WHERE script_id = ? AND mechanic IS NULL AND segment_index IN ({','.join(map(str, REPLACE_INDICES))})",
        (SCRIPT_ID,)
    ).fetchall()

    for seg in segments:
        print(f"    > Seg {seg['segment_index']}: Extraction... ", end="", flush=True)
        extracted = extract_mechanic(seg["segment_text"])
        
        games      = extracted.get("games", [])
        mechanic   = extracted.get("mechanic") or "unknown"
        moment     = extracted.get("moment") or "gameplay"
        queries    = extracted.get("search_queries", [])
        game_title = games[0] if games else None
        
        conn.execute(
            "UPDATE asset_briefs SET game_title = ?, mechanic = ?, moment = ?, search_query = ? WHERE id = ?",
            (game_title, mechanic, moment, json.dumps(queries), seg["id"])
        )
        conn.commit()
        print(f"DONE. Queries: {queries[:1]}")

    # 3. Re-Source and Re-Review
    print(f"\n  [P4d] Step 2: Re-sourcing and Vision Auditing...")
    print(f"| {'Seg':<3} | {'New Source':<15} | {'Decision':<10} | {'Review Reason':<40} |")
    print("|" + "-"*5 + "|" + "-"*17 + "|" + "-"*12 + "|" + "-"*42 + "|")
    
    # Reload cleaned segments
    segments = conn.execute(
        f"SELECT * FROM asset_briefs WHERE script_id = ? AND status = 'pending' AND segment_index IN ({','.join(map(str, REPLACE_INDICES))})",
        (SCRIPT_ID,)
    ).fetchall()

    results = []
    for seg in segments:
        # a) Source
        source_res = source_asset_for_segment(seg)
        
        # Update local dict for review
        seg["selected_asset"] = source_res["path"]
        seg["asset_source"] = source_res.get("source")
        
        # b) Review (Soft Prompt is now in core.asset_reviewer)
        # Custom offsets (Priority 1 logic)
        review_offset = 0.3 if seg["segment_index"] == 2 else 0.5
        review = evaluate_asset(seg, offset_pct=review_offset)
        decision = review.get("decision", "SKIP")
        
        # c) Persist
        conn.execute(
            "UPDATE asset_briefs SET status = 'sourced', selected_asset = ?, asset_source = ?, review_status = ?, review_reason = ?, review_confidence = ? WHERE id = ?",
            (source_res["path"], source_res.get("source"), decision, review.get("reason"), review.get("confidence"), seg["id"])
        )
        conn.commit()
        
        print(f"| {seg['segment_index']:<3} | {str(source_res.get('source')):<15} | {decision:<10} | {str(review.get('reason')):<40} |")
        results.append(decision)

    conn.close()

    # 4. Final Summary & Threshold Check
    conn = get_connection()
    stats = conn.execute("SELECT review_status, COUNT(*) as count FROM asset_briefs WHERE script_id = ? GROUP BY review_status", (SCRIPT_ID,)).fetchall()
    conn.close()
    
    total_accept = 0
    print("\n" + "="*80)
    print("FINAL PIPELINE READINESS (Script 1)")
    print("="*80)
    for s in stats:
        print(f"  {s[0]:<10}: {s[1]}")
        if s[0] == "ACCEPT": total_accept = s[1]
    
    if total_accept >= 14:
        print(f"\n✓ THRESHOLD MET: {total_accept}/15 segments ACCEPTED.")
        print("🚀 EXECUTING STAGE P7: FINAL ASSEMBLY...")
        import subprocess
        subprocess.run(["python", "stage_p7_assemble.py"], check=True)
    else:
        print(f"\n⚠ THRESHOLD NOT MET: Only {total_accept}/15 segments ACCEPTED.")
        print("Manual intervention required for remaining REPLACE/SKIP segments.")

if __name__ == "__main__":
    main()

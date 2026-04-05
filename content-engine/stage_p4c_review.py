import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from core.db import get_connection
from core.asset_reviewer import evaluate_asset, generate_visual_description
from core.inventory_manager import add_asset

def main():
    parser = argparse.ArgumentParser(description="Stage P4c: Image Review Agent")
    parser.add_argument("--script_id", type=int, default=1, help="Script ID to review assets for")
    args = parser.parse_args()

    print(f"\n======================================================================")
    print(f"ContentEngine P4c — Asset Review Agent (Script {args.script_id})")
    print(f"======================================================================")

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    # 1. Fetch segments to review
    # We review segments where status='sourced' and selected_asset is present.
    segments = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = ? AND status = 'sourced' AND selected_asset IS NOT NULL",
        (args.script_id,)
    ).fetchall()
    
    if not segments:
        print(f"  [REVIEW] No sourced assets found for Script {args.script_id}.")
        return

    print(f"  [REVIEW] Sourcing complete. Reviewing {len(segments)} assets...")
    
    start_time = time.time()
    results = []
    
    # Stats counters
    stats = {"ACCEPT": 0, "REPLACE": 0, "SKIP": 0}

    for seg in segments:
        seg_idx = seg.get("segment_index", "?")
        asset_name = Path(seg["selected_asset"]).name
        print(f"  > Seg {seg_idx} | {asset_name} | game={seg.get('game_title') or '[Abstract]'}...")
        
        # Call the review agent
        review = evaluate_asset(seg)
        
        # Auto-SKIP if confidence < 0.5
        decision = review.get("decision", "SKIP")
        confidence = review.get("confidence", 0.0)
        
        if decision == "REPLACE" and confidence < 0.5:
            decision = "SKIP"
            review["reason"] = f"Auto-SKIP: Low confidence ({confidence}) | " + review.get("reason", "")
            
        stats[decision] = stats.get(decision, 0) + 1
        
        # Update DB
        conn.execute(
            "UPDATE asset_briefs SET review_status = ?, review_reason = ?, review_confidence = ? WHERE id = ?",
            (decision, review.get("reason"), confidence, seg["id"])
        )
        conn.commit()
        
        review["segment_index"] = seg_idx
        review["game_title"] = seg.get("game_title", "N/A")
        review["asset_path"] = seg["selected_asset"]
        
        # --- INVENTORY ACTION ---
        visual_desc = ""
        inv_action = "REJECTED"
        if decision == "ACCEPT":
            print(f"    [Inventory] Indexing visual description... ", end="", flush=True)
            visual_desc = generate_visual_description(seg["selected_asset"])
            print("DONE.")
            inv_action = "ADDED"
            
        success = add_asset(seg, review, visual_description=visual_desc)
        review["inventory_action"] = inv_action if success else "FAILED"
        review["visual_description"] = visual_desc
        
        results.append(review)

    duration = time.time() - start_time
    
    # 2. Terminal Summary
    print(f"\n----------------------------------------------------------------------")
    print(f"REVIEW SUMMARY (Script {args.script_id})")
    print(f"----------------------------------------------------------------------")
    print(f"  ACCEPTED:  {stats['ACCEPT']} segments")
    print(f"  REPLACE:   {stats['REPLACE']} segments")
    print(f"  SKIP:      {stats['SKIP']} segments")
    print(f"\n  REPLACE segments (for Director):")
    
    replaces = [r for r in results if r["decision"] == "REPLACE"]
    if not replaces:
        print(f"  None.")
    for r in replaces:
        seg_idx = r.get("segment_index") if r.get("segment_index") is not None else "?"
        game = r.get("game_title") or "N/A"
        reason = r.get("reason") or "No reason provided"
        conf = r.get("confidence") if isinstance(r.get("confidence"), (int, float)) else 0.0
        print(f"  seg {str(seg_idx):<2} | {str(game):<20} | {str(reason):<40} | conf: {conf:.2f}")
        
    print(f"\n  Total review time: {duration:.1f}s")
    print(f"----------------------------------------------------------------------")

    # 3. Save Markdown Report
    report_path = Path("output") / f"review_{args.script_id}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Asset Review Report — Script {args.script_id}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Stats\n- **ACCEPTED**: {stats['ACCEPT']}\n- **REPLACE**: {stats['REPLACE']}\n- **SKIP**: {stats['SKIP']}\n\n")
        
        f.write(f"## Review Details\n\n")
        f.write("| Seg | Game | Decision | Confidence | Reason | Asset |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for r in results:
            seg_idx = r.get("segment_index") if r.get("segment_index") is not None else "?"
            game = r.get("game_title") or "N/A"
            reason = r.get("reason") or "No reason provided"
            conf = r.get("confidence") if isinstance(r.get("confidence"), (int, float)) else 0.0
            asset = Path(r["asset_path"]).as_uri()
            f.write(f"| {seg_idx} | {game} | **{r['decision']}** | {conf:.2f} | {reason} | [Link]({asset}) |\n")

        f.write(f"\n## Inventory Actions\n\n")
        f.write("| Seg | Action | Asset Type | Visual Description (Preview) |\n")
        f.write("| :--- | :--- | :--- | :--- |\n")
        for r in results:
            action = r.get("inventory_action", "SKIP")
            ext = Path(r["asset_path"]).suffix.lower()
            a_type = "clip" if ext == ".mp4" else "image"
            desc = r.get("visual_description", "")[:60] + "..." if r.get("visual_description") else "-"
            f.write(f"| {r['segment_index']} | {action} | {a_type} | {desc} |\n")

    print(f"✓ Summary report saved to: {report_path}")
    conn.close()

if __name__ == "__main__":
    main()

import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PYTHONIOENCODING"] = "utf-8"

from core.db import get_connection
from core.asset_sourcer import _build_pollinations_prompt

def preview(indices):
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    with open("scripts/preview_subset_out.txt", "w", encoding="utf-8") as f:
        f.write("=== MICRO-VERIFICATION PREVIEW ===\n")
        for idx in indices:
            seg = conn.execute(
                "SELECT * FROM asset_briefs WHERE script_id = 1 AND segment_index = ?", (idx,)
            ).fetchone()
            
            if not seg:
                f.write(f"\nSEGMENT {idx}: Not found in DB\n")
                continue
                
            poll_prompt = _build_pollinations_prompt(seg)
            
            f.write(f"\nSEGMENT {idx}:\n")
            f.write(f"  game_title : {seg.get('game_title')!r}\n")
            f.write(f"  mechanic   : {seg.get('mechanic')!r}\n")
            f.write(f"  moment     : {seg.get('moment')!r}\n")
            f.write(f"  Final Prompt: {poll_prompt}\n")
            
        f.write("\n=== END PREVIEW ===\n")
    conn.close()

if __name__ == "__main__":
    preview([0, 3, 7])

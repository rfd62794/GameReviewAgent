import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["PYTHONIOENCODING"] = "utf-8"

from core.db import get_connection
from core.asset_sourcer import _build_pollinations_prompt

def full_preview():
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    segments = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = 1 ORDER BY segment_index"
    ).fetchall()
    
    with open("_preview_all_out.txt", "w", encoding="utf-8") as f:
        f.write("=== FINAL MVP POLLINATIONS PREVIEW (ALL 15 SEGMENTS) ===\n")
        f.write(f"{'seg':<4} | {'game':<20} | {'mechanic':<25} | {'moment':<30} | {'pollinations_prompt'}\n")
        f.write("-" * 120 + "\n")
        
        for seg in segments:
            idx = str(seg['segment_index'])
            game = str(seg['game_title'] or "None")[:20]
            mech = str(seg['mechanic'] or "None")[:25]
            mom = str(seg['moment'] or "None")[:30]
            prompt = _build_pollinations_prompt(seg)
            f.write(f"{idx:<4} | {game:<20} | {mech:<25} | {mom:<30} | {prompt}\n")
            
        f.write("-" * 120 + "\n")
        f.write("=== END PREVIEW ===\n")
    conn.close()

if __name__ == "__main__":
    full_preview()

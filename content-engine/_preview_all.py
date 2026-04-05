import sys, os
sys.path.insert(0, ".")
os.environ["PYTHONIOENCODING"] = "utf-8"

from core.db import get_connection
from core.asset_sourcer import _build_pollinations_prompt

def full_preview():
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    segments = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = 1 ORDER BY segment_index"
    ).fetchall()
    
    # Calculate widths for the table
    w_seg = 4
    w_game = 20
    w_mech = 25
    w_moment = 30
    w_prompt = 80
    
    # Table header
    header = f"{'seg':<{w_seg}} | {'game':<{w_game}} | {'mechanic':<{w_mech}} | {'moment':<{w_moment}} | {'pollinations_prompt':<{w_prompt}}"
    separator = "-" * len(header)
    
    print("\n=== FINAL MVP POLLINATIONS PREVIEW (ALL 15 SEGMENTS) ===")
    print(header)
    print(separator)
    
    for seg in segments:
        s_idx = str(seg['segment_index'])
        game = str(seg['game_title'] or "None")[:w_game-3] + "..." if len(str(seg['game_title'] or "None")) > w_game else str(seg['game_title'] or "None")
        mech = str(seg['mechanic'] or "None")[:w_mech-3] + "..." if len(str(seg['mechanic'] or "None")) > w_mech else str(seg['mechanic'] or "None")
        moment = str(seg['moment'] or "None")[:w_moment-3] + "..." if len(str(seg['moment'] or "None")) > w_moment else str(seg['moment'] or "None")
        prompt = _build_pollinations_prompt(seg)
        
        # Truncate prompt for table view but keep it readable
        p_display = prompt if len(prompt) < w_prompt else prompt[:w_prompt-3] + "..."
        
        print(f"{s_idx:<{w_seg}} | {game:<{w_game}} | {mech:<{w_mech}} | {moment:<{w_moment}} | {p_display}")
    
    conn.close()
    print(separator)
    print("=== END PREVIEW ===")

if __name__ == "__main__":
    full_preview()

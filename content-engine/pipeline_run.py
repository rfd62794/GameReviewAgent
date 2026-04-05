import sys
import subprocess
import os
import time
from pathlib import Path

from core.db import get_connection

def run_step(script_name: str):
    print(f"\n[{script_name.upper()}] Starting...")
    try:
        res = subprocess.run([sys.executable, script_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[{script_name.upper()}] Failed with exit code {e.returncode}. Continuing...")

def print_summary(start_time: float):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT segment_index, asset_source, ai_image_prompt, search_query, "
        "game_title, mechanic, estimated_duration_s "
        "FROM asset_briefs WHERE script_id = 1 ORDER BY segment_index ASC"
    )
    rows = cursor.fetchall()
    conn.close()

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"{'SEG':<4} | {'GAME':<20} | {'MECHANIC':<20} | {'SOURCE':<12} | {'DUR':>4}s")
    print("-" * 70)

    counts = {"ai_generated": 0, "pexels": 0, "wikimedia": 0, "local": 0, "pending": 0, "fallback": 0}
    for row in rows:
        seg_idx, source, prompt, query, game, mechanic, dur = row
        game    = (game or "")[:20]
        mechanic = (mechanic or "")[:20]
        src_label = source if source else "pending"
        print(f"{seg_idx:<4} | {game:<20} | {mechanic:<20} | {src_label:<12} | {dur:>4}")
        key = source if source in counts else "pending"
        counts[key] = counts.get(key, 0) + 1

    print()
    print("SOURCING TOTALS:")
    for k, v in counts.items():
        if v: print(f"  {k}: {v}")

    vid_path = Path("output/video_1.mp4")
    if vid_path.exists():
        size_mb = vid_path.stat().st_size / (1024 * 1024)
        print(f"\nFINAL VIDEO : {vid_path.absolute()}")
        print(f"FILE SIZE   : {size_mb:.2f} MB")
    else:
        print("\nFINAL VIDEO: NOT FOUND — assembly may have failed.")

    print(f"TOTAL TIME  : {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print("=" * 70)

if __name__ == "__main__":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PATH"] = str(Path().absolute()) + os.pathsep + os.environ.get("PATH", "")
    os.environ["SCRIPT_ID"] = "1"
    start = time.time()
    run_step("stage_p3b_segment.py")
    run_step("stage_p4_extract.py")
    run_step("stage_p4b_source.py")
    run_step("stage_p6_audio.py")
    run_step("stage_p7_assemble.py")
    print_summary(start)

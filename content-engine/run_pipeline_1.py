import sys
import subprocess
import os
from pathlib import Path

from core.db import get_connection

def run_step(script_name: str):
    print(f"\n[{script_name.upper()}] Starting...")
    try:
        res = subprocess.run([sys.executable, script_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[{script_name.upper()}] Failed with exit code {e.returncode}. Continuing...")

def print_summary():
    conn = get_connection()
    cursor = conn.execute("SELECT segment_index, asset_source, ai_image_prompt, search_query FROM asset_briefs WHERE script_id = 1 ORDER BY segment_index ASC")
    rows = cursor.fetchall()
    conn.close()
    
    print("\n---------------------------------------------------------")
    print("FINAL SUMMARY TABLE")
    print("---------------------------------------------------------")
    print(f"{'SEG':<4} | {'SOURCE':<10} | {'QUERY/PROMPT':<40}")
    print("-" * 57)
    
    counts = {"youtube": 0, "pollinations": 0, "wikimedia": 0, "local": 0, "pending": 0}
    for row in rows:
        seg_idx, source, prompt, query = row
        val = prompt if source == "ai_image" else query
        val = (val[:37] + "...") if val and len(val) > 40 else val
        print(f"{seg_idx:<4} | {source if source else 'pending':<10} | {val}")
        
        if source == "youtube": counts["youtube"] += 1
        elif source == "ai_image": counts["pollinations"] += 1
        elif source == "wikimedia": counts["wikimedia"] += 1
        elif source == "local": counts["local"] += 1
        else: counts["pending"] += 1

    print("\nSOURCING TOTALS:")
    print(f"YouTube clips: {counts['youtube']}")
    print(f"Pollinations stills: {counts['pollinations']}")
    print(f"Wikimedia: {counts['wikimedia']}")
    print(f"Local: {counts['local']}")
    print(f"Pending/Failed: {counts['pending']}")

    vid_path = Path("output/video_1.mp4")
    if vid_path.exists():
        size_mb = vid_path.stat().st_size / (1024 * 1024)
        print(f"\nFINAL VIDEO: {vid_path.absolute()} ({size_mb:.2f} MB)")
    else:
        print("\nFINAL VIDEO: Not found.")

if __name__ == "__main__":
    os.environ["PATH"] = str(Path().absolute()) + os.pathsep + os.environ.get("PATH", "")
    os.environ["SCRIPT_ID"] = "1"
    run_step("run_p3b.py")
    run_step("run_p4.py")
    run_step("run_p6.py")
    run_step("run_p7.py")
    print_summary()

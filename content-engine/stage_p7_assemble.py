"""
ContentEngine P7 — Visual Assembly Orchestration

Orchestrates FFmpeg to process all sourced assets (Ken Burns, scale, trim),
concatenates audio tracks, and multiplexes into the final MP4.
"""

import sys
import subprocess
from pathlib import Path
import shutil
from core.db import get_connection
from core.inventory_manager import increment_usage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.assembler import preprocess_segment, assemble_video

SCRIPT_ID = 1

import yaml

def main():
    print("=" * 70)
    print("ContentEngine P7 — FFmpeg Assembly")
    print("=" * 70)
    print()

    # Paths
    engine_root = Path(__file__).resolve().parent
    temp_dir = engine_root / "temp"
    output_dir = engine_root / "output"
    audio_dir = engine_root / "audio"
    config_path = engine_root / "config.yaml"
    
    # Load config
    with open(config_path, "r", encoding="utf-8") as f:
        config_full = yaml.safe_load(f)
        config = config_full.get("assembly", {})

    # Cleanup temp
    if temp_dir.exists(): shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    cursor = conn.execute(
        "SELECT * FROM asset_briefs WHERE script_id = ? AND status = 'sourced' ORDER BY segment_index",
        (SCRIPT_ID,)
    )
    segments = cursor.fetchall()
    conn.close()

    if not segments:
        print(f"✗ No sourced segments found for Script ID {SCRIPT_ID}.")
        sys.exit(1)

    print(f"[1/3] Preprocessing {len(segments)} visual segments...")
    proc_segments = []
    
    for seg in segments:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"  > Processing {label} ({seg['estimated_duration_s']}s) ... ", flush=True)
        
        out_file = preprocess_segment(seg, temp_dir, config)
        if out_file:
            print(f"      ✓ {out_file.name}")
            seg["temp_file"] = out_file
            proc_segments.append(seg)
        else:
            print("      ✗ FAILED")
            sys.exit(1)

    print("\n[2/3] Preparing audio track...")
    # Concat hook + body audio
    hook_audio = audio_dir / f"script_{SCRIPT_ID}_hook.mp3"
    body_audio = audio_dir / f"script_{SCRIPT_ID}_body.mp3"
    full_audio = temp_dir / "full_audio.mp3"
    
    audio_concat = temp_dir / "audio_concat.txt"
    with open(audio_concat, "w") as f:
        if hook_audio.exists(): f.write(f"file '{hook_audio.resolve()}'\n")
        if body_audio.exists(): f.write(f"file '{body_audio.resolve()}'\n")
        
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat),
        "-c", "copy", str(full_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("      ✓ Audio concatenated")

    print("\n[3/3] Assembling final video...")
    output_video = output_dir / f"video_{SCRIPT_ID}.mp4"
    assemble_video(proc_segments, full_audio, output_video, temp_dir, config)
    
    print(f"      ✓ Assembled: {output_video.name}")
    if (output_dir / f"video_{SCRIPT_ID}.srt").exists():
        print(f"      ✓ Subtitles: video_{SCRIPT_ID}.srt")
        
    # --- INVENTORY USAGE UPDATE ---
    print("\n[4/4] Updating inventory usage stats...")
    for seg in proc_segments:
        if seg.get("selected_asset"):
            increment_usage(seg["selected_asset"])
    print("      ✓ Usage stats updated")

    print("\n" + "=" * 70)
    print("ASSEMBLY COMPLETE")
    print(f"Output: {output_video}")
    print("=" * 70)

if __name__ == "__main__":
    main()

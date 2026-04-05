"""
ContentEngine P7 — Visual Assembly Orchestration

Orchestrates FFmpeg to process all sourced assets (Ken Burns, scale, trim),
concatenates audio tracks, and multiplexes into the final MP4.
"""

import argparse
import sys
import subprocess
import shutil
import yaml
from pathlib import Path
from core.db import get_connection
from core.inventory_manager import increment_usage

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.assembler import preprocess_segment, assemble_video, get_ffmpeg_path

def main():
    parser = argparse.ArgumentParser(description="ContentEngine P7 — Visual Assembly")
    parser.add_argument("--script_id", type=int, default=1, help="Script ID to assemble")
    parser.add_argument("--output_name", type=str, default=None, help="Base name for output files (e.g. video_2)")
    args = parser.parse_args()

    script_id = args.script_id
    output_base = args.output_name if args.output_name else f"video_{script_id}"

    print("=" * 70)
    print(f"ContentEngine P7 — FFmpeg Assembly (Script {script_id})")
    print("=" * 70)
    print()

    # Paths
    engine_root = Path(__file__).resolve().parent
    temp_dir = engine_root / "temp"
    output_dir = engine_root / "output"
    config_path = engine_root / "config.yaml"
    
    # Audio search paths
    audio_search_dirs = [
        engine_root / "audio",
        engine_root / "assets" / "audio",
        engine_root / "output"
    ]
    
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
        (script_id,)
    )
    segments = cursor.fetchall()
    conn.close()

    if not segments:
        print(f"✗ No sourced segments found for Script ID {script_id}.")
        sys.exit(1)

    print(f"[1/4] Preprocessing {len(segments)} visual segments...")
    proc_segments = []
    
    for seg in segments:
        label = "HOOK" if seg["segment_index"] == 0 else f"BODY {seg['segment_index']}"
        print(f"  > Processing {label} ({seg['estimated_duration_s']}s) ... ", end="", flush=True)
        
        out_file = preprocess_segment(seg, temp_dir, config)
        if out_file:
            print(f"✓ {out_file.name}")
            seg["temp_file"] = out_file
            proc_segments.append(seg)
        else:
            print("✗ FAILED")
            sys.exit(1)

    print("\n[2/4] Preparing audio track...")
    # Find hook + body audio
    hook_audio = None
    body_audio = None
    for ad in audio_search_dirs:
        h = ad / f"script_{script_id}_hook.mp3"
        b = ad / f"script_{script_id}_body.mp3"
        if h.exists(): hook_audio = h
        if b.exists(): body_audio = b
        
    if not hook_audio or not body_audio:
        print(f"✗ Audio files not found for Script {script_id} (Looked in: {[str(d) for d in audio_search_dirs]})")
        sys.exit(1)
        
    full_audio = temp_dir / "full_audio.mp3"
    audio_concat = temp_dir / "audio_concat.txt"
    with open(audio_concat, "w") as f:
        f.write(f"file '{hook_audio.resolve()}'\n")
        f.write(f"file '{body_audio.resolve()}'\n")
        
    subprocess.run([
        get_ffmpeg_path(), "-y", "-f", "concat", "-safe", "0", "-i", str(audio_concat),
        "-c", "copy", str(full_audio)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"      ✓ Audio concatenated: {hook_audio.name} + {body_audio.name}")

    print("\n[3/4] Assembling final video...")
    output_video = output_dir / f"{output_base}.mp4"
    assemble_video(proc_segments, full_audio, output_video, temp_dir, config)
    
    print(f"      ✓ Assembled: {output_video.name}")
    if (output_dir / f"{output_base}.srt").exists():
        print(f"      ✓ Subtitles: {output_base}.srt")
        
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

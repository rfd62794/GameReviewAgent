"""
ContentEngine P6 — First Audio Generation Run

Director-authorized audio run.
Reads approved script from DB → generates audio via Edge TTS →
saves as separate hook and body MP3 files.

Edge TTS selected for Phase 1 validation (zero cost, no API key).
ElevenLabs upgrade path preserved per SDD — voice engine is swappable.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection

import edge_tts

# --- Configuration ---
VOICE = "en-US-GuyNeural"
OUTPUT_DIR = Path(__file__).resolve().parent / "audio"
SCRIPT_ID = 1


async def generate_audio(text: str, output_path: Path, label: str) -> dict:
    """
    Generate audio from text using Edge TTS.
    
    Args:
        text: Script text to synthesize.
        output_path: Path to save the MP3 file.
        label: Human label for logging ("hook" or "body").
    
    Returns:
        Dict with file_path, file_size_bytes, and label.
    """
    print(f"  Generating {label}...", flush=True)

    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(str(output_path))

    file_size = output_path.stat().st_size
    print(f"  ✓ {label} saved: {output_path.name} ({file_size:,} bytes)", flush=True)

    return {
        "label": label,
        "file_path": str(output_path),
        "file_size_bytes": file_size,
    }


async def main():
    print("=" * 70)
    print("ContentEngine P6 — First Audio Generation Run")
    print("=" * 70)
    print()

    # --- Step 1: Mark script as approved ---
    print("[1/3] Setting script approval flag...", flush=True)
    conn = get_connection()
    conn.execute(
        "UPDATE scripts SET approved = 1 WHERE id = ?", (SCRIPT_ID,)
    )
    conn.commit()
    print(f"       scripts.approved = 1 for script_id = {SCRIPT_ID}", flush=True)
    print()

    # --- Step 2: Fetch script text ---
    print("[2/3] Loading script from database...", flush=True)
    row = conn.execute(
        "SELECT hook_short_script, mid_form_body, word_count_hook, word_count_body "
        "FROM scripts WHERE id = ?",
        (SCRIPT_ID,),
    ).fetchone()
    conn.close()

    if not row:
        print(f"✗ Script ID {SCRIPT_ID} not found.")
        sys.exit(1)

    hook_text = row["hook_short_script"]
    body_text = row["mid_form_body"]
    hook_wc = row["word_count_hook"]
    body_wc = row["word_count_body"]

    print(f"       Hook: {hook_wc} words, {len(hook_text)} characters", flush=True)
    print(f"       Body: {body_wc} words, {len(body_text)} characters", flush=True)
    print(f"       Total characters: {len(hook_text) + len(body_text)}", flush=True)
    print()

    # --- Step 3: Generate audio ---
    print(f"[3/3] Generating audio via Edge TTS...", flush=True)
    print(f"       Voice: {VOICE}", flush=True)
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    hook_path = OUTPUT_DIR / "script_1_hook.mp3"
    body_path = OUTPUT_DIR / "script_1_body.mp3"

    hook_result = await generate_audio(hook_text, hook_path, "hook_short_script")
    body_result = await generate_audio(body_text, body_path, "mid_form_body")

    print()

    # --- Report ---
    print("=" * 70)
    print("AUDIO GENERATION REPORT")
    print("=" * 70)
    print()
    print(f"  Voice:        {VOICE}")
    print(f"  Engine:       Edge TTS (Microsoft Neural)")
    print(f"  Format:       MP3")
    print()
    print(f"  ┌─────────────────────┬──────────────┬──────────────┐")
    print(f"  │ File                │ Size         │ Words        │")
    print(f"  ├─────────────────────┼──────────────┼──────────────┤")
    print(f"  │ script_1_hook.mp3   │ {hook_result['file_size_bytes']:>10,} B │ {hook_wc:>12} │")
    print(f"  │ script_1_body.mp3   │ {body_result['file_size_bytes']:>10,} B │ {body_wc:>12} │")
    print(f"  └─────────────────────┴──────────────┴──────────────┘")
    print()
    print(f"  Output directory: {OUTPUT_DIR}")
    print()
    print("=" * 70)
    print("AUDIO COMPLETE — Awaiting Director review.")
    print("Play both files. Do not proceed to further pipeline stages.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

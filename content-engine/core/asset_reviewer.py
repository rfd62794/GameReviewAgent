import os
import json
import base64
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from core.llm_client import create_llm_client

logger = logging.getLogger(__name__)

# Paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
FFMPEG_PATH = _PROJECT_ROOT / "ffmpeg.exe"
TEMP_DIR = _PROJECT_ROOT / "assets" / "temp_review"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are reviewing a video asset for a YouTube channel about game mechanics.
Your goal is to ensure the visual quality and relevance of the asset.

Respond with JSON only:
{
  "decision": "ACCEPT" | "REPLACE" | "SKIP",
  "confidence": 0.0-1.0,
  "reason": "max 80 chars"
}"""

def extract_review_frame(asset_path: str, offset_pct: float = 0.5) -> Optional[str]:
    """
    Extract a representative frame from a video or use the image path directly.
    For videos, extracts at offset_pct of duration (default 50%).
    """
    path = Path(asset_path)
    if not path.exists():
        logger.error(f"Asset path does not exist: {asset_path}")
        return None

    if path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
        return str(path)

    if path.suffix.lower() == ".mp4":
        # 1. Get duration
        try:
            cmd_dur = [
                str(FFMPEG_PATH), "-i", str(path), "-hide_banner"
            ]
            # FFmpeg prints duration to stderr
            res = subprocess.run(cmd_dur, capture_output=True, text=True)
            match = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", res.stderr)
            if not match:
                duration = 5 # fallback
            else:
                h, m, s = float(match.group(1)), float(match.group(2)), float(match.group(3))
                duration = h * 3600 + m * 60 + s
            
            # 2. Extract frame at offset_pct
            timestamp = duration * offset_pct
            out_name = f"review_{path.stem}_at_{int(offset_pct*100)}.jpg"
            out_path = TEMP_DIR / out_name
            
            cmd_extract = [
                str(FFMPEG_PATH), "-y",
                "-ss", str(timestamp),
                "-i", str(path),
                "-vframes", "1",
                "-q:v", "2",
                str(out_path)
            ]
            subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return str(out_path)
        except Exception as e:
            logger.error(f"Failed to extract frame from {asset_path}: {e}")
            return None
            
    return None

def evaluate_asset(segment: dict, offset_pct: float = 0.5) -> dict:
    """
    Evaluate the asset for a given segment using Gemini Vision.
    Returns: {"decision": "ACCEPT"|... , "reason": "...", "confidence": 0.0}
    """
    asset_path = segment.get("selected_asset")
    if not asset_path:
        return {"decision": "SKIP", "reason": "No asset found", "confidence": 1.0}

    frame_path = extract_review_frame(asset_path, offset_pct=offset_pct)
    if not frame_path:
        return {"decision": "SKIP", "reason": "Could not extract frame", "confidence": 1.0}

    # Encode image
    try:
        with open(frame_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return {"decision": "SKIP", "reason": f"B64 encode failed: {e}", "confidence": 1.0}

    # Build prompt
    prompt = (
        f"SEGMENT TEXT: {segment.get('segment_text')}\n"
        f"GAME: {segment.get('game_title') or 'abstract concept'}\n"
        f"MECHANIC: {segment.get('mechanic')}\n"
        f"VISUAL MOMENT: {segment.get('moment')}\n\n"
        "Evaluate whether this asset appropriately illustrates the segment. Consider:\n"
        "1. Is the correct game visible? (if game-specific)\n"
        "2. Does it show the mechanic described?\n"
        "3. Is it visually clear and high quality?\n"
        "4. Is it suitable for a professional YouTube video?\n\n"
        "CRITICAL CONSTRAINT: If the video shows hands on a controller, a person's face, or "
        "physically blocks the game UI — always return REPLACE regardless of other factors."
    )

    client = create_llm_client(model="google/gemini-2.5-flash")
    try:
        res = client.generate_vision(
            prompt=prompt,
            b64_img=b64_img,
            system_prompt=SYSTEM_PROMPT
        )
        
        # Parse JSON
        text = res.get("text", "{}")
        # Strip potential markdown fences
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            review = json.loads(match.group())
        else:
            review = json.loads(text)
            
        return review
    except Exception as e:
        logger.error(f"Vision evaluation failed for segment {segment.get('segment_index')}: {e}")
        return {"decision": "SKIP", "reason": f"Evaluation error: {e}", "confidence": 0.0}

import re # added back after being missed in manual typing

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

    # Build source-aware prompt context
    source = segment.get("asset_source", "unknown")
    game = segment.get("game_title")
    is_abstract = game is None
    
    prompt = (
        f"SEGMENT TEXT: {segment.get('segment_text')}\n"
        f"GAME: {game or '[Abstract Concept]'}\n"
        f"MECHANIC: {segment.get('mechanic')}\n"
        f"VISUAL MOMENT: {segment.get('moment')}\n"
        f"ASSET SOURCE: {source}\n\n"
        "### REVIEW CRITERIA (Source-Aware):\n"
    )
    
    if is_abstract and source == "ai_generated":
        prompt += (
            "1. THIS IS AN ABSTRACT CONCEPT SEGMENT with an AI-generated infographic.\n"
            "2. ACCEPT if the image is visually professional, high quality, and generally relevant.\n"
            "3. NEVER reject ('REPLACE') for being 'too generic' or 'metaphorical'.\n"
            "4. Only REPLACE if the image is corrupted, blank, or completely nonsensical.\n"
        )
    elif not is_abstract and source == "ai_generated":
        prompt += (
            "1. THIS IS A GAME-SPECIFIC SEGMENT using an AI fallback (no real footage was found).\n"
            "2. This is a CONCEPTUAL ILLUSTRATION, not a literal screenshot.\n"
            "3. ACCEPT if it illustrates the mechanic or moment effectively.\n"
            "4. DO NOT reject for failing to look exactly like the UI of the specified game.\n"
        )
    else:
        prompt += (
            "1. THIS IS A REAL ASSET (YouTube/Wiki/Local).\n"
            "2. Check for exact game matching, mechanic accuracy, and professional quality.\n"
            "3. APPLY STRICT STANDARDS for franchise accuracy.\n"
        )

    prompt += (
        "\nCRITICAL CONSTRAINT: If the video/image shows human hands on a controller, "
        "a person's face, or physically blocks the game UI — always return REPLACE."
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

def generate_visual_description(asset_path: str) -> str:
    """
    Generate a plain-English visual description of the asset for semantic search.
    """
    frame_path = extract_review_frame(asset_path, offset_pct=0.5)
    if not frame_path:
        return "No visual data available."

    try:
        with open(frame_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Failed to encode image: {e}"

    prompt = (
        "Describe this video game screenshot/clip in plain English for a search index. "
        "Focus on: \n"
        "1. Specific UI elements and text visible.\n"
        "2. Key game characters or objects.\n"
        "3. Overall color palette and lighting.\n"
        "4. The specific action or mechanic being demonstrated.\n\n"
        "Format: A concise, descriptive sentence or two. Do not use conversational text."
    )

    client = create_llm_client(model="google/gemini-2.5-flash")
    try:
        res = client.generate_vision(
            prompt=prompt,
            b64_img=b64_img,
            system_prompt="You are a professional game asset cataloger."
        )
        return res.get("text", "Description unavailable.").strip()
    except Exception as e:
        logger.error(f"Visual description generation failed: {e}")
        return "Failed to generate description."

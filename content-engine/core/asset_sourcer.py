import os
import re
import yaml
import requests
import urllib.parse
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
USER_AGENT = "ContentEngine/1.0 (rfditservices.com)"

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOCAL_GAMEPLAY_DIR = ASSETS_DIR / "gameplay"
DL_DIR = ASSETS_DIR / "downloads"
GENERATED_DIR = ASSETS_DIR / "generated"

LOCAL_GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
DL_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# --- Config flags ---
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
        _cfg = yaml.safe_load(_f)
    CONFIG = _cfg.get("assembly", {})
except Exception:
    CONFIG = {}

YOUTUBE_CLIP_ENABLED = CONFIG.get("youtube_clip_enabled", True)

from core.youtube_sourcer import source_for_segment as yt_source
from core.llm_client import create_llm_client
from core.reference_manager import get_reference
from core.prompt_builder import (
    build_pollinations_prompt, 
    build_variant_prompts
)


def download_file(url: str, output_path: Path) -> Path:
    """Download a file from an active URL."""
    r = requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=15)
    r.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def check_local_gameplay(query: str) -> str | None:
    """Check if we have a locally captured gameplay clip matching the query."""
    q_norm = query.lower().strip()
    for file in LOCAL_GAMEPLAY_DIR.glob("*.mp4"):
        if q_norm in file.name.lower():
            return str(file)
    return None


def search_wikimedia(query: str, segment_id: int) -> str | None:
    """Search Wikimedia Commons for images."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "generator": "search",
        "gsrsearch": f"File:{query}",
        "gsrlimit": 1,
        "pithumbsize": 1920
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=15)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        if pages:
            first_page = list(pages.values())[0]
            image_url = first_page.get("thumbnail", {}).get("source")
            if image_url:
                out_path = DL_DIR / f"wiki_seg_{segment_id}.jpg"
                return str(download_file(image_url, out_path))
    except Exception as e:
        print(f"Wikimedia error: {e}")
    return None





def search_pexels_image(query: str, segment_id: int) -> str | None:
    """Search Pexels for a stock image."""
    if not PEXELS_API_KEY:
        return None
        
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    try:
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        photos = data.get("photos", [])
        if photos:
            img_url = photos[0].get("src", {}).get("large2x")
            if img_url:
                out_path = DL_DIR / f"pexels_img_seg_{segment_id}.jpg"
                return str(download_file(img_url, out_path))
    except Exception as e:
        print(f"Pexels Image error: {e}")
    return None


def _make_fallback_frame(segment_id: int) -> str:
    """Generate a solid dark-blue #1a1a2e frame via FFmpeg as last-resort fallback."""
    import subprocess
    out_path = DL_DIR / f"fallback_seg_{segment_id}.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=#1a1a2e:s=1920x1080:r=1",
        "-frames:v", "1",
        str(out_path)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"    [FALLBACK] Dark-blue frame generated: {out_path.name}")
        return str(out_path)
    except Exception as e:
        print(f"    [FALLBACK FAILED] FFmpeg color frame error: {e}")
        return None


from core.db import get_connection
from core.prompt_engineer import generate_visual_prompt

def generate_ai_image(prompt: str, segment_id: int, game_title: Optional[str] = None, mechanic: Optional[str] = None, moment: Optional[str] = None) -> Dict[str, Any] | None:
    """Generate image(s) using OpenRouter multimodal models. Supports grounding references."""
    # Load config
    model = "google/gemini-2.5-flash-image"
    aspect_ratio = "16:9"
    variant_count = CONFIG.get("image_variant_count", 1)
    refs_enabled = CONFIG.get("reference_images_enabled", True)
    
    _models_path = Path(__file__).resolve().parent.parent / "models.yaml"
    try:
        with open(_models_path, "r", encoding="utf-8") as f:
            m_cfg = yaml.safe_load(f)
            model = m_cfg.get("models", {}).get("p4_image_gen", model)
            aspect_ratio = m_cfg.get("image_config", {}).get("aspect_ratio_midform", aspect_ratio)
    except:
        pass

    # 1. Fetch style_notes for grounding (if game provided)
    style_notes = None
    if game_title:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT style_notes FROM game_clip_index WHERE game_title = ? LIMIT 1", 
                (game_title,)
            ).fetchone()
            if row:
                style_notes = row["style_notes"]
        finally:
            conn.close()

    # 2. Prompt Engineering Stage (DeepSeek)
    if game_title and mechanic and moment:
        optimized_prompt = generate_visual_prompt(game_title, mechanic, moment, style_notes)
        print(f"    [Prompt Engineer] Optimized: {optimized_prompt[:80]}...")
    else:
        optimized_prompt = prompt

    # 3. Grounding Reference (Mechanic-aware)
    ref_bytes = None
    if game_title and refs_enabled:
        ref_bytes = get_reference(game_title, mechanic)
        msg_context = f"'{game_title} {mechanic}'" if mechanic else f"'{game_title}'"
        if ref_bytes:
            print(f"    [OpenRouter AI] Using style reference for {msg_context}")
        else:
            print(f"    [OpenRouter AI] No reference found for {msg_context} — using text-only")

    # 4. Multi-variant generation (if cycling enabled)
    # We use segment_id + index for unique naming
    paths = []
    client = create_llm_client(model=model)
    
    # Simple heuristic to determine variant count
    prompts = [optimized_prompt]
    if variant_count > 1:
        modifiers = ["close-up detail", "wide shot", "dramatic angle"]
        for i in range(1, variant_count):
            mod = modifiers[i % len(modifiers)]
            prompts.append(f"{optimized_prompt}, {mod}")

    for i, p in enumerate(prompts):
        suffix = f"_v{i}" if variant_count > 1 else ""
        out_path = GENERATED_DIR / f"ai_img_seg_{segment_id}{suffix}.png"
        
        try:
            print(f"    [OpenRouter AI] Generating variant {i} for segment {segment_id}...")
            image_bytes = client.generate_image(
                prompt=p,
                aspect_ratio=aspect_ratio,
                image_size="2K",
                model=model,
                reference_bytes=ref_bytes
            )
            
            if image_bytes:
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                paths.append(str(out_path))
                size_kb = out_path.stat().st_size // 1024
                print(f"    [OpenRouter AI] OK — {size_kb}KB ({out_path.name})")
        except Exception as e:
            print(f"    [OpenRouter AI] Variant {i} FAILED: {e}")

    if not paths:
        return None
        
    return {
        "paths": paths, 
        "reference_used": 1 if ref_bytes else 0,
        "variant_count": len(paths)
    }


def source_asset_for_segment(segment: dict) -> dict:
    """
    Take an asset_brief segment and return the path and source of the best asset.

    MVP mode (youtube_clip_enabled: false):
      Every segment → Pollinations AI still with a game-context prompt.
      No YouTube calls. No Wikimedia calls.

    Full mode (youtube_clip_enabled: true):
      Standard priority chain: local → YouTube → Wikimedia → Pexels → Pollinations.
    """
    vtype = segment["visual_type"]
    query = segment.get("search_query", "")
    seg_id = segment["id"]

    # ── MVP MODE: Pollinations-only ──────────────────────────────────────────
    if not YOUTUBE_CLIP_ENABLED:
        game_title = segment.get("game_title")
        mechanic   = segment.get("mechanic")
        moment     = segment.get("moment")
        
        poll_prompt = build_pollinations_prompt(game_title, mechanic, moment)
        
        # NOTE: drawtext_string construction moved to stage_p4b_source.py
        # This function no longer handles filtering strings.

        print(f"\n{'='*60}")
        print(f"  SEG {segment.get('segment_index')} | game={game_title or '(none)'} | mechanic={mechanic or '(none)'}")
        print(f"  Pollinations Prompt: {poll_prompt}")

        res = generate_ai_image(poll_prompt, seg_id, game_title, mechanic)
        if not res:
            print(f"  [FALLBACK] AI generation failed — using dark-blue frame")
            fallback_path = _make_fallback_frame(seg_id)
            if fallback_path:
                return {"path": fallback_path, "source": "ai_generated", "paths": [fallback_path]}
            return {"path": None, "source": None}

        return {
            "path": res["paths"][0], 
            "source": "ai_generated", 
            "paths": res["paths"],
            "reference_used": res["reference_used"],
            "variant_count": res["variant_count"]
        }

    # ── FULL MODE (Skip if YouTube disabled) ─────────────────────────────────
    if not YOUTUBE_CLIP_ENABLED:
        return {"path": None, "source": None}

    prompt = segment.get("ai_image_prompt", "")

    # 1. Gameplay Clip & Stock Clip — YouTube primary
    if vtype in ["gameplay_clip", "stock_clip"]:
        local = check_local_gameplay(query)
        if local:
            return {"path": local, "source": "local"}

        yt_res = yt_source(segment)
        if yt_res:
            return {"path": yt_res["path"], "source": yt_res["source"]}

        wiki = search_wikimedia(query, seg_id)
        if wiki:
            return {"path": wiki, "source": "wikimedia"}

    # 2. Stock Image — Pexels
    if vtype == "stock_still":
        pex_img = search_pexels_image(query, seg_id)
        if pex_img:
            return {"path": pex_img, "source": "pexels"}

    # 3. AI Image / universal fallback
    poll_prompt = _build_pollinations_prompt(segment) if not prompt else prompt
    res = generate_ai_image(poll_prompt, seg_id, segment.get("game_title"), segment.get("mechanic"))
    if res:
        return {
            "path": res["paths"][0], 
            "source": "ai_image",
            "paths": res["paths"],
            "reference_used": res["reference_used"],
            "variant_count": res["variant_count"]
        }

    return {"path": None, "source": None}

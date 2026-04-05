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
from core.db import get_connection
from core.prompt_builder import (
    build_pollinations_prompt, 
    build_infographic_prompt
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

from core.db import get_connection
from core.prompt_engineer import generate_visual_prompt
from core.wiki_sourcer import find_game_slug, search_game_page, get_page_images, download_image

def generate_ai_image(prompt: str, segment_id: int, game_title: Optional[str] = None, mechanic: Optional[str] = None, moment: Optional[str] = None) -> Dict[str, Any] | None:
    """
    Generate image(s) using OpenRouter text-to-image.
    Strictly for abstract concepts or last-resort fallback. No grounding.
    """
    # Load config
    model = "google/gemini-2.5-flash-image"
    aspect_ratio = "16:9"
    variant_count = CONFIG.get("image_variant_count", 1)
    
    _models_path = Path(__file__).resolve().parent.parent / "models.yaml"
    try:
        with open(_models_path, "r", encoding="utf-8") as f:
            m_cfg = yaml.safe_load(f)
            model = m_cfg.get("models", {}).get("p4_image_gen", model)
            aspect_ratio = m_cfg.get("image_config", {}).get("aspect_ratio_midform", aspect_ratio)
    except:
        pass

    # 1. Prompt Engineering Stage (DeepSeek)
    style_notes = None
    if game_title:
        conn = get_connection()
        row = conn.execute("SELECT style_notes FROM game_clip_index WHERE game_title = ?", (game_title,)).fetchone()
        if row: style_notes = row["style_notes"]
        conn.close()

    if game_title and mechanic and moment:
        optimized_prompt = generate_visual_prompt(game_title, mechanic, moment, style_notes)
    else:
        optimized_prompt = prompt

    # 2. Multi-variant generation
    paths = []
    client = create_llm_client(model=model)
    
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
            print(f"    [OpenRouter AI] Generating variant {i}...")
            image_bytes = client.generate_image(
                prompt=p,
                aspect_ratio=aspect_ratio,
                image_size="2K",
                model=model
            )
            
            if image_bytes:
                with open(out_path, "wb") as f:
                    f.write(image_bytes)
                paths.append(str(out_path))
        except Exception as e:
            print(f"    [OpenRouter AI] FAILED: {e}")

    if not paths: return None
        
    return {
        "paths": paths, 
        "variant_count": len(paths)
    }


def source_wiki_screenshot(game_title: str, mechanic: str, segment_id: int) -> str | None:
    """Source an authentic screenshot from the game wiki."""
    slug = find_game_slug(game_title)
    
    # 1. Try mechanic-specific page
    page = search_game_page(game_title, slug, mechanic)
    if not page:
        # 2. Fallback to main game page
        page = search_game_page(game_title, slug)
        
    if not page: return None
    
    urls = get_page_images(page, slug)
    if not urls: return None
    
    # Take the first high-res image
    for url in urls:
        img_bytes = download_image(url)
        if img_bytes:
            out_path = ASSETS_DIR / "wiki" / f"seg_{segment_id}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(img_bytes)
            return str(out_path)
            
    return None


def source_asset_for_segment(segment: dict) -> dict:
    """
    Route to the best available asset based on context.
    Priority: Local -> YouTube -> Wiki -> AI Fallback.
    """
    game_title = segment.get("game_title")
    mechanic = segment.get("mechanic")
    moment = segment.get("moment")
    seg_id = segment["id"]
    seg_idx = segment.get("segment_index", "?")
    
    print(f"\n--- ROUTING SEGMENT {seg_idx} | game={game_title or '[Abstract]'} ---")

    # 1. GAME-SPECIFIC CHAIN
    if game_title:
        # a) Local Gameplay
        local = check_local_gameplay(f"{game_title} {mechanic}")
        if local:
            print(f"  [ROUTING] Match found in local library: {Path(local).name}")
            return {"path": local, "source": "local", "paths": [local]}
            
        # b) YouTube Clip
        print(f"  [ROUTING] Attempting YouTube capture...")
        yt_res = yt_source(segment)
        if yt_res:
            print(f"  [ROUTING] YouTube SUCCESS: {Path(yt_res['path']).name}")
            return {"path": yt_res["path"], "source": "youtube", "paths": [yt_res["path"]]}
            
        # c) Wiki Screenshot
        print(f"  [ROUTING] Attempting Wiki screenshot...")
        wiki_path = source_wiki_screenshot(game_title, mechanic, seg_id)
        if wiki_path:
            print(f"  [ROUTING] Wiki SUCCESS: {Path(wiki_path).name}")
            return {"path": wiki_path, "source": "wikimedia", "paths": [wiki_path]}
            
        # d) AI Fallback (Game context, but last resort)
        print(f"  [ROUTING] Real assets failed. Falling back to AI...")
        prompt = f"{game_title} {mechanic}, {moment}, game screenshot style"
        res = generate_ai_image(prompt, seg_id, game_title, mechanic, moment)
        if res:
            return {"path": res["paths"][0], "source": "ai_generated", "paths": res["paths"]}

    # 2. ABSTRACT CHAIN
    else:
        print(f"  [ROUTING] Abstract segment. Starting with AI generation...")
        prompt = segment.get("ai_image_prompt") or build_infographic_prompt(segment.get("segment_text"))
        res = generate_ai_image(prompt, seg_id)
        if res:
            return {"path": res["paths"][0], "source": "ai_generated", "paths": res["paths"]}
            
    # 3. ABSOLUTE FALLBACK
    print(f"  [ROUTING] ALL SOURCES FAILED. Using dark-blue frame.")
    fallback = _make_fallback_frame(seg_id)
    return {"path": fallback, "source": "ai_generated", "paths": [fallback]}

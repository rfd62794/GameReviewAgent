import os
import re
import yaml
import requests
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
USER_AGENT = "ContentEngine/1.0 (rfditservices.com)"

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOCAL_GAMEPLAY_DIR = ASSETS_DIR / "gameplay"
DL_DIR = ASSETS_DIR / "downloads"

from core.youtube_sourcer import source_for_segment as yt_source

LOCAL_GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
DL_DIR.mkdir(parents=True, exist_ok=True)

# --- Config flags ---
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
        _cfg = yaml.safe_load(_f)
    YOUTUBE_CLIP_ENABLED = _cfg.get("assembly", {}).get("youtube_clip_enabled", True)
except Exception:
    YOUTUBE_CLIP_ENABLED = True


def _build_pollinations_prompt(segment: dict) -> str:
    """Build a Pollinations art prompt from segment metadata per MVP directive."""
    text = segment.get("segment_text", "")
    query = segment.get("search_query", "")
    prompt = segment.get("ai_image_prompt", "")

    # Use existing ai_image_prompt if one was set during segmentation
    if prompt:
        return prompt

    # Otherwise derive from segment text — extract game title / mechanic heuristics
    text_lower = text.lower()
    game = None
    mechanic = None

    if "cookie clicker" in text_lower:
        game = "Cookie Clicker"
    elif "adventure capitalist" in text_lower:
        game = "AdVenture Capitalist"
    elif query and query not in ("gaming", ""):
        game = query.title()

    # Mechanic keywords
    for kw in ["idle", "clicker", "prestige", "ascension", "multiplier", "resource", "loop", "upgrade"]:
        if kw in text_lower:
            mechanic = kw
            break

    if game and mechanic:
        return f"{game} {mechanic} moment digital art, vibrant game UI screenshot style, 4K"
    elif game:
        return f"{game} gameplay digital art, vibrant, high quality"
    elif mechanic:
        return f"{mechanic} game design concept art, vivid colors, premium illustration"
    else:
        return "video game design concept art, vivid digital illustration, high quality, dark mode"


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


def generate_pollinations_image(prompt: str, segment_id: int) -> str | None:
    """Generate a fallback image using Pollinations.ai HTTP GET."""
    if not prompt: return None
    
    # URL encode the prompt
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true"
    
    try:
        out_path = DL_DIR / f"ai_img_seg_{segment_id}.jpg"
        return str(download_file(url, out_path))
    except Exception as e:
        print(f"Pollinations error: {e}")
    return None


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
        poll_prompt = _build_pollinations_prompt(segment)
        print(f"  [MVP] Pollinations prompt → {poll_prompt}")
        ai = generate_pollinations_image(poll_prompt, seg_id)
        if ai:
            return {"path": ai, "source": "ai_image"}
        return {"path": None, "source": None}

    # ── FULL MODE ────────────────────────────────────────────────────────────
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
    ai = generate_pollinations_image(poll_prompt, seg_id)
    if ai:
        return {"path": ai, "source": "ai_image"}

    return {"path": None, "source": None}

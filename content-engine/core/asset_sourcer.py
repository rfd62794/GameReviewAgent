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
    """
    Build a Pollinations art prompt from mechanic extractor output stored in asset_briefs.

    Priority:
      1. ai_image_prompt — set by segmentation for 'ai_image' type segments
      2. game_title + moment from extractor → "{game} {moment} digital art, ..."
      3. mechanic only → "{mechanic} game mechanic concept art, ..."
      4. generic fallback
    """
    # 1. Use ai_image_prompt if segmentation already craft one
    existing = segment.get("ai_image_prompt")
    if existing:
        return existing

    # 2. Read extractor output columns directly
    game_title = segment.get("game_title")  # e.g. "Cookie Clicker"
    mechanic   = segment.get("mechanic")    # e.g. "prestige"
    moment     = segment.get("moment")      # e.g. "ascension button press"

    if game_title and moment:
        return f"{game_title} {moment} digital art, vibrant game UI screenshot style, 4K"
    elif game_title and mechanic:
        return f"{game_title} {mechanic} moment digital art, vibrant game UI screenshot style, 4K"
    elif game_title:
        return f"{game_title} gameplay digital art, vibrant, high quality, 4K"
    elif mechanic:
        return f"{mechanic} game mechanic concept art, vivid digital illustration, 4K"
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


def generate_pollinations_image(prompt: str, segment_id: int, timeout: int = 45) -> str | None:
    """Generate an image using Pollinations.ai HTTP GET. Retries once on failure."""
    if not prompt:
        return None

    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1920&height=1080&nologo=true"
    out_path = DL_DIR / f"ai_img_seg_{segment_id}.jpg"

    for attempt in (1, 2):
        try:
            r = requests.get(url, timeout=timeout, stream=True)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "")
            content_length = int(r.headers.get("Content-Length", 0))
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            size_kb = out_path.stat().st_size // 1024
            print(f"    [Pollinations] attempt {attempt}: OK — {content_type} {size_kb}KB ({out_path.name})")
            return str(out_path)
        except Exception as e:
            print(f"    [Pollinations] attempt {attempt} FAILED: {e}")
            if attempt == 1:
                print(f"    [Pollinations] retrying...")

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
        seg_idx = segment.get("segment_index", seg_id)
        game    = segment.get("game_title") or "(none)"
        mechanic = segment.get("mechanic") or "(none)"
        from core.assembler import _extract_key_phrase, _escape_drawtext
        key_phrase = _extract_key_phrase(segment.get("segment_text", ""))
        escaped    = _escape_drawtext(key_phrase)
        drawtext_str = (
            f"drawbox=x=0:y=810:w=iw:h=140:color=black@0.55:t=fill,"
            f"drawtext=text='{escaped}':fontsize=52:fontcolor=white"
            f":x=(w-text_w)/2:y=840:shadowcolor=black@0.6:shadowx=2:shadowy=2"
        )

        print(f"\n{'='*60}")
        print(f"  SEG {seg_idx} | game={game} | mechanic={mechanic}")
        print(f"  Pollinations prompt: {poll_prompt}")
        print(f"  Drawtext           : \"{key_phrase}\"")

        ai = generate_pollinations_image(poll_prompt, seg_id)
        if not ai:
            print(f"  [FALLBACK] Pollinations failed both attempts — using dark-blue frame")
            ai = _make_fallback_frame(seg_id)

        if ai:
            return {"path": ai, "source": "ai_generated"}
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

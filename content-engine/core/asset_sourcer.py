import os
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
    Implements P4 and P4b selection logic.
    """
    vtype = segment["visual_type"]
    query = segment["search_query"]
    prompt = segment["ai_image_prompt"]
    req_dur = segment["estimated_duration_s"]
    seg_id = segment["id"]

    # 1. Gameplay Clip & Stock Clip priority (now both use YouTube heavily)
    if vtype in ["gameplay_clip", "stock_clip"]:
        local = check_local_gameplay(query)
        if local: return {"path": local, "source": "local"}
        
        yt_res = yt_source(segment)
        if yt_res: 
            return {"path": yt_res["path"], "source": yt_res["source"]}
            
        wiki = search_wikimedia(query, seg_id)
        if wiki: return {"path": wiki, "source": "wikimedia"}
        
    # 2. Stock Image priority
    if vtype == "stock_still":
        pex_img = search_pexels_image(query, seg_id)
        if pex_img: return {"path": pex_img, "source": "pexels"}
        
    # 3. AI Image priority or strict fallback wrapper
    if vtype == "ai_image" or True: # Fallback applies to everything if above fails
        ai = generate_pollinations_image(prompt or f"Abstract representation of {query}, high quality, clean", seg_id)
        if ai: return {"path": ai, "source": "ai_generated"}
        
    return {"path": None, "source": None}

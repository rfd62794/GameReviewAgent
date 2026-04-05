import requests
import re
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

USER_AGENT = "ContentEngine/1.0 (rfditservices.com)"

def find_game_slug(game_title: str) -> str:
    """
    Normalize "Cookie Clicker" -> "cookieclicker".
    Checks if fandom.com/api.php responds to the slug.
    """
    # 1. Clean title: lowercase, remove non-alphanumeric
    slug = re.sub(r'[^a-zA-Z0-9]', '', game_title).lower()
    
    # Try basic slug first
    if _check_slug(slug):
        return slug
    
    # Try hyphenated variant: "cookie-clicker"
    hyphen_slug = re.sub(r'\s+', '-', game_title).lower()
    hyphen_slug = re.sub(r'[^a-z0-9\-]', '', hyphen_slug)
    if _check_slug(hyphen_slug):
        return hyphen_slug
        
    return slug # fallback to basic string even if 404, acquire_reference will fail later

def _check_slug(slug: str) -> bool:
    """Check if the Fandom API exists for this slug."""
    url = f"https://{slug}.fandom.com/api.php"
    try:
        r = requests.get(url, params={"action": "query", "meta": "siteinfo", "format": "json"}, timeout=5)
        return r.status_code == 200
    except:
        return False

def search_game_page(game_title: str, game_slug: str, mechanic: Optional[str] = None) -> Optional[str]:
    """Search for the main game page or mechanic page on the wiki. Returns page title."""
    url = f"https://{game_slug}.fandom.com/api.php"
    
    # Normalize mechanic: snake_case -> spaces
    mech_norm = mechanic.replace("_", " ") if mechanic else None
    query = f"{game_title} {mech_norm}" if mech_norm else game_title
    
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": 1
    }
    try:
        r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        data = r.json()
        search_results = data.get("query", {}).get("search", [])
        if search_results:
            return search_results[0].get("title")
    except Exception as e:
        logger.error(f"Wiki search failed for {game_title}: {e}")
    return None

def get_page_images(page_title: str, game_slug: str) -> List[str]:
    """Get high-resolution image URLs from a page."""
    api_url = f"https://{game_slug}.fandom.com/api.php"
    
    # 1. Get image names from page
    params = {
        "action": "query",
        "titles": page_title,
        "prop": "images",
        "format": "json"
    }
    try:
        r = requests.get(api_url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            logger.warning(f"No pages found for title {page_title} on {game_slug}")
            return []
            
        first_page = list(pages.values())[0]
        images = first_page.get("images", [])
        image_titles = [img["title"] for img in images if not img["title"].lower().endswith(('.svg', '.ico', '.gif'))]
        
        if not image_titles:
            logger.warning(f"No valid image titles found on {page_title}")
            return []

        # 2. Get info for each image
        image_urls = []
        for title in image_titles[:10]: # Check first 10
            info_params = {
                "action": "query",
                "titles": title,
                "prop": "imageinfo",
                "iiprop": "url|size|dimensions",
                "format": "json"
            }
            ir = requests.get(api_url, params=info_params, headers={"User-Agent": USER_AGENT}, timeout=10)
            idata = ir.json()
            ipages = idata.get("query", {}).get("pages", {})
            if ipages:
                iface = list(ipages.values())[0]
                info_list = iface.get("imageinfo", [])
                if not info_list:
                    continue
                info = info_list[0]
                url = info.get("url")
                width = info.get("width", 0)
                # Loosen to 400px for style reference
                if url and width >= 400:
                    image_urls.append(url)
                    
        return image_urls
    except Exception as e:
        logger.error(f"Wiki image fetch failed for {page_title}: {e}")
    return []

def download_image(url: str) -> Optional[bytes]:
    """Download image raw bytes. Validates minimum size."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            content = r.content
            if len(content) > 10240: # > 10KB
                return content
    except Exception as e:
        logger.error(f"Image download failed: {e}")
    return None

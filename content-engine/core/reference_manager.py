import os
import re
import sqlite3
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict

# googlesearch requirement
from googlesearch import search

# Local imports
from core.db import get_connection
from core.wiki_sourcer import (
    find_game_slug, 
    search_game_page, 
    get_page_images, 
    download_image
)

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
REFERENCE_DIR = ASSETS_DIR / "references"
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

def get_reference(game_title: str) -> Optional[bytes]:
    """Retrieve existing reference from disk or initiate acquisition."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT reference_image_path FROM game_clip_index WHERE game_title = ?", 
            (game_title,)
        )
        row = cursor.fetchone()
        if row and row["reference_image_path"]:
            path = Path(row["reference_image_path"])
            if path.exists():
                with open(path, "rb") as f:
                    return f.read()
                    
        # Not found or invalid path, try acquisition
        return acquire_reference(game_title)
    finally:
        conn.close()

def acquire_reference(game_title: str) -> Optional[bytes]:
    """Grounding priority chain: Wiki -> Clip Frame -> Google Images -> Flag."""
    print(f"    [Acquiring Reference] {game_title}...")
    
    # 1. Wiki Priority
    game_slug = find_game_slug(game_title)
    page_title = search_game_page(game_title, game_slug)
    if page_title:
        image_urls = get_page_images(page_title, game_slug)
        if image_urls:
            img_bytes = download_image(image_urls[0])
            if img_bytes:
                print(f"      ✓ SUCCESS [Wiki]: {game_slug}/{page_title}")
                store_reference(game_title, img_bytes)
                return img_bytes

    # 2. Clip Frame Extraction
    frame_bytes = extract_clip_frame(game_title)
    if frame_bytes:
        print(f"      ✓ SUCCESS [Clip Frame]: {game_title}")
        store_reference(game_title, frame_bytes)
        return frame_bytes
        
    # 3. Google Images Fallback
    try:
        query = f"{game_title} gameplay screenshot"
        # From googlesearch-python: search returns iterator of URLs
        results = search(query, num_results=1)
        first_url = next(results, None)
        if first_url:
            img_bytes = download_image(first_url)
            if img_bytes:
                print(f"      ✓ SUCCESS [Google Images]: {first_url}")
                store_reference(game_title, img_bytes)
                return img_bytes
    except Exception as e:
        logger.error(f"Google search failed for {game_title}: {e}")

    # 4. Flag for Director
    flag_for_director(game_title)
    return None

def store_reference(game_title: str, image_bytes: bytes) -> str:
    """Save reference to disk and update DB."""
    slug = re.sub(r'[^a-zA-Z0-9]', '_', game_title).lower()
    path = REFERENCE_DIR / f"{slug}.png"
    
    with open(path, "wb") as f:
        f.write(image_bytes)
        
    conn = get_connection()
    try:
        # Update all existing rows for this game to ensure style consistency
        cursor = conn.execute(
            "UPDATE game_clip_index SET reference_image_path = ? WHERE game_title = ?",
            (str(path), game_title)
        )
        
        # If no rows were updated, insert a new entry
        if cursor.rowcount == 0:
            conn.execute(
                """
                INSERT INTO game_clip_index (game_title, reference_image_path, mechanic, search_query)
                VALUES (?, ?, 'N/A', 'N/A')
                """,
                (game_title, str(path))
            )
        conn.commit()
    finally:
        conn.close()
        
    return str(path)

def extract_clip_frame(game_title: str) -> Optional[bytes]:
    """FFmpeg frame extraction from existing clips."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT search_query FROM game_clip_index WHERE game_title = ? AND search_query LIKE '%.mp4'",
            (game_title,)
        )
        row = cursor.fetchone()
        if row and row["search_query"]:
            clip_path = Path(row["search_query"])
            if clip_path.exists():
                # Extract at 10% of duration (or 5s if unknown)
                out_path = REFERENCE_DIR / "temp_frame.png"
                cmd = [
                    "ffmpeg", "-y", "-ss", "5", "-i", str(clip_path),
                    "-vframes", "1", str(out_path)
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if out_path.exists():
                    f_bytes = out_path.read_bytes()
                    out_path.unlink()
                    return f_bytes
    except Exception as e:
        logger.error(f"Clip frame extraction failed for {game_title}: {e}")
    finally:
        conn.close()
    return None

def flag_for_director(game_title: str) -> None:
    """Set needs_reference=1 in DB."""
    print(f"      ✗ FAILED to find reference for {game_title}. Flagging for Director.")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE game_clip_index SET needs_reference = 1 WHERE game_title = ?", 
            (game_title,)
        )
        conn.commit()
    finally:
        conn.close()

import re # needed for store_reference

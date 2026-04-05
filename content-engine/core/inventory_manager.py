import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from core.db import get_connection

logger = logging.getLogger(__name__)

def add_asset(segment_data: dict, review_data: dict, visual_description: str = "") -> bool:
    """
    Persist an asset to the inventory after review.
    Handles both ACCEPTED and REJECTED assets (negative caching).
    """
    conn = get_connection()
    asset_path = segment_data.get("selected_asset")
    if not asset_path:
        return False
        
    try:
        # Determine asset type from extension
        ext = Path(asset_path).suffix.lower()
        asset_type = "clip" if ext == ".mp4" else "image"
        
        # Map decision to allowed database statuses
        decision_raw = review_data.get("decision", "pending").upper()
        if decision_raw == "ACCEPT":
            status = "accepted"
        elif decision_raw in ["REPLACE", "SKIP"]:
            status = "rejected"
        else:
            status = "pending"
            
        # Use segment and review data to populate
        conn.execute("""
        INSERT OR REPLACE INTO asset_inventory (
            asset_path, asset_type, source, game_title, mechanic, moment,
            review_status, review_confidence, review_reason, visual_description,
            segment_text_sample, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asset_path,
            asset_type,
            segment_data.get("asset_source", "unknown"),
            segment_data.get("game_title"),
            segment_data.get("mechanic"),
            segment_data.get("moment"),
            status,
            review_data.get("confidence", 0.0),
            review_data.get("reason"),
            visual_description,
            segment_data.get("segment_text", "")[:100],
            datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Failed to add asset to inventory: {e}")
        return False
    finally:
        conn.close()

def check_inventory(game_title: str, mechanic: str) -> Optional[dict]:
    """
    Check for an existing, accepted asset for a game+mechanic.
    Returns metadata dict if found, else None.
    """
    if not game_title or not mechanic:
        return None
        
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT asset_path, asset_type, game_title, mechanic, 
                   visual_description, times_used, source
            FROM asset_inventory 
            WHERE game_title = ? 
              AND mechanic = ? 
              AND review_status = 'accepted'
            ORDER BY times_used ASC, review_confidence DESC
            LIMIT 1
        """, (game_title, mechanic)).fetchone()
        
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def find_by_description(query_text: str, limit: int = 5) -> List[dict]:
    """
    Keyword-based search against visual_description (Semantic Fallback).
    
    # TODO: Upgrade to SQLite FTS5 or vector embeddings when inventory > 500 assets
    """
    if not query_text:
        return []
        
    # Extract keywords (Split on spaces, filter words > 3 chars)
    keywords = [w.strip(",.!?").lower() for w in query_text.split() if len(w) > 3]
    if not keywords:
        return []
        
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    results = {} # asset_path -> data
    try:
        for keyword in keywords:
            rows = conn.execute("""
                SELECT asset_path, asset_type, game_title, mechanic, 
                       visual_description, times_used, source
                FROM asset_inventory 
                WHERE review_status = 'accepted'
                  AND visual_description LIKE ?
                ORDER BY times_used ASC, review_confidence DESC
                LIMIT ?
            """, (f"%{keyword}%", limit)).fetchall()
            
            for r in rows:
                results[r["asset_path"]] = dict(r)
                
        # Deduplicate and limit
        final_list = list(results.values())[:limit]
        return final_list
    finally:
        conn.close()

def increment_usage(asset_path: str):
    """Update usage statistics for an asset."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE asset_inventory 
            SET times_used = times_used + 1,
                last_used_at = ?
            WHERE asset_path = ?
        """, (datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'), asset_path))
        conn.commit()
    finally:
        conn.close()

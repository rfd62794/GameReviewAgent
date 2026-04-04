"""
P3b: Transcript Segmentation Logic

Splits the generated script into visual segments based on paragraph boundaries,
estimates duration, assigns visual types, and generates search/AI prompts.
"""

import math
import re

WORDS_PER_SECOND = 2.8

# Simple keyword heuristics for visual type assignment
GAMEPLAY_KEYWORDS = ["cookie clicker", "adventure capitalist", "kongregate", "orteil", "heavenly chips", "ascension button", "gameplay", "idle game", "run"]
ABSTRACT_KEYWORDS = ["psychology", "math", "fallacy", "loss aversion", "emotion", "euphoria", "anxiety", "frustration", "design", "concept", "paradox"]
AI_KEYWORDS = ["abstract", "system", "structure", "growth", "multiplier", "collateral", "decision space"]


def _estimate_duration(text: str) -> int:
    """Estimate audio duration in seconds for a text segment."""
    word_count = len(text.split())
    # Round up to ensure we have enough visual duration
    seconds = math.ceil(word_count / WORDS_PER_SECOND)
    return max(3, seconds)  # Provide at least 3 seconds


def _assign_visual_metadata(text: str, tags: list[str]) -> dict:
    """Analyze segment text to assign visual type and generate prompts."""
    text_lower = text.lower()
    
    # 1. Check for specific gameplay mentions
    if any(k in text_lower for k in GAMEPLAY_KEYWORDS):
        # Extract which game if possible, else default to generic idle gameplay
        query = "idle game gameplay"
        if "cookie clicker" in text_lower: query = "cookie clicker"
        elif "adventure capitalist" in text_lower: query = "adventure capitalist"
        
        return {
            "visual_type": "gameplay_clip",
            "search_query": query,
            "ai_image_prompt": None
        }
        
    # 2. Check for abstract/emotional concepts (good for AI or abstract stock)
    if any(k in text_lower for k in ABSTRACT_KEYWORDS):
        return {
            "visual_type": "ai_image",
            "search_query": "",
            "ai_image_prompt": f"Minimalist clean infographic style illustration representing {text.split('.')[0]}. Dark mode colors, premium."
        }
        
    # 3. Check for systemic/structural concepts
    if any(k in text_lower for k in AI_KEYWORDS):
        return {
            "visual_type": "stock_still",
            "search_query": "technology abstract",
            "ai_image_prompt": None
        }
        
    # 4. Default fallback
    return {
        "visual_type": "stock_clip",
        "search_query": "gaming",
        "ai_image_prompt": None
    }


def segment_script(script_id: int, hook_text: str, body_text: str, tags: list[str]) -> list[dict]:
    """
    Break script into paragraph segments and annotate with visual metadata.
    Segment 0 is always the hook. Paragraphs of body form segments 1..N.
    """
    segments = []
    
    # Process Segment 0: Hook
    hook_meta = _assign_visual_metadata(hook_text, tags)
    # Hooks usually benefit from high-energy clips
    hook_meta["visual_type"] = "stock_clip" if hook_meta["visual_type"] == "stock_still" else hook_meta["visual_type"]
    
    segments.append({
        "script_id": script_id,
        "segment_index": 0,
        "segment_text": hook_text,
        "estimated_duration_s": _estimate_duration(hook_text),
        "visual_type": hook_meta["visual_type"],
        "search_query": hook_meta["search_query"],
        "ai_image_prompt": hook_meta["ai_image_prompt"]
    })
    
    # Process Body (split by double newline to get paragraphs)
    # Strip whitespace to avoid empty trailing segments
    body_paragraphs = [p.strip() for p in body_text.strip().split('\n\n') if p.strip()]
    
    for i, paragraph in enumerate(body_paragraphs, start=1):
        meta = _assign_visual_metadata(paragraph, tags)
        segments.append({
            "script_id": script_id,
            "segment_index": i,
            "segment_text": paragraph,
            "estimated_duration_s": _estimate_duration(paragraph),
            "visual_type": meta["visual_type"],
            "search_query": meta["search_query"],
            "ai_image_prompt": meta["ai_image_prompt"]
        })
        
    return segments

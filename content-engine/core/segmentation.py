"""
P3b: Transcript Segmentation Logic

Splits the generated script into visual segments based on paragraph boundaries,
estimates duration, assigns visual types, and generates search/AI prompts.
"""

import math
import re

WORDS_PER_SECOND = 2.8

def _estimate_duration(text: str) -> int:
    """Estimate audio duration in seconds for a text segment."""
    word_count = len(text.split())
    # Round up to ensure we have enough visual duration
    seconds = math.ceil(word_count / WORDS_PER_SECOND)
    return max(3, seconds)  # Provide at least 3 seconds


def segment_script(script_id: int, hook_text: str, body_text: str, tags: list[str]) -> list[dict]:
    """
    Break script into paragraph segments.
    Segment 0 is always the hook. Paragraphs of body form segments 1..N.
    
    Returns a list of dicts with: 
    script_id, segment_index, segment_text, estimated_duration_s
    """
    segments = []
    
    # Process Segment 0: Hook
    segments.append({
        "script_id": script_id,
        "segment_index": 0,
        "segment_text": hook_text,
        "estimated_duration_s": _estimate_duration(hook_text)
    })
    
    # Process Body (split by double newline to get paragraphs)
    body_paragraphs = [p.strip() for p in body_text.strip().split('\n\n') if p.strip()]
    
    for i, paragraph in enumerate(body_paragraphs, start=1):
        segments.append({
            "script_id": script_id,
            "segment_index": i,
            "segment_text": paragraph,
            "estimated_duration_s": _estimate_duration(paragraph)
        })
        
    return segments

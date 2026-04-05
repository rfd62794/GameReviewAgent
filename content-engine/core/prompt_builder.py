import re

def extract_key_phrase(segment_text: str, max_words: int = 9) -> str:
    """
    Extract a concise key phrase from segment text for video overlays.
    
    1. Take the first sentence.
    2. Remove trailing punctuation.
    3. Truncate to max_words.
    """
    if not segment_text:
        return ""
    
    # Take first sentence
    sentence_match = re.split(r'(?<=[.!?])\s+', segment_text.strip())
    first = sentence_match[0].strip() if sentence_match else segment_text.strip()
    
    # Drop trailing punctuation
    first = first.rstrip(".!?,;:")
    
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words])
    
    return first


def _escape_drawtext(text: str) -> str:
    """Escape characters for FFmpeg drawtext filter."""
    # Escape backslash, colon, single-quote
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def build_drawtext_string(key_phrase: str) -> str:
    """
    Build the full FFmpeg filter string for the text overlay.
    Includes a semi-transparent black bar and white centered text.
    """
    if not key_phrase:
        return ""
        
    escaped = _escape_drawtext(key_phrase)
    # Bar: y=810 (bottom third of 1080), h=140
    # Text: fontsize 52, y=840 (centered in bar)
    return (
        f"drawbox=x=0:y=810:w=iw:h=140:color=black@0.55:t=fill,"
        f"drawtext=text='{escaped}':fontsize=52:fontcolor=white"
        f":x=(w-text_w)/2:y=840:shadowcolor=black@0.6:shadowx=2:shadowy=2"
    )


def build_pollinations_prompt(game_title: str, mechanic: str, moment: str) -> str:
    """
    Build a Pollinations AI image prompt from mechanic metadata.
    
    MVP Logic:
      - If game_title: "{game_tile} {moment} digital art, vibrant game UI screenshot style, 4K"
      - Otherwise: "{mechanic} {moment} concept art, dark mode digital illustration, 4K"
    """
    moment_val = moment or "gameplay scene"
    
    if game_title:
        return f"{game_title} {moment_val} digital art, vibrant game UI screenshot style, 4K"
    elif mechanic:
        return f"{mechanic} {moment_val} concept art, dark mode digital illustration, 4K"
    else:
        return "video game design concept art, vivid digital illustration, high quality, dark mode"


def build_infographic_prompt(segment_text: str) -> str:
    """
    Build a minimalist infographic style prompt for abstract segments.
    """
    if not segment_text:
        return "minimalist clean infographic illustration, dark mode colors, premium"
        
    # Use first sentence/clause for context
    context = segment_text.split('.')[0].strip()
    return f"Minimalist clean infographic style illustration representing {context}. Dark mode colors, premium."

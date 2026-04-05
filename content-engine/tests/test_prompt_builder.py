import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.prompt_builder import (
    extract_key_phrase,
    build_drawtext_string,
    build_pollinations_prompt,
    build_infographic_prompt
)

def test_extract_key_phrase():
    text = "Normally, sunk cost traps players. This leads to anxiety and frustration."
    phrase = extract_key_phrase(text)
    assert phrase == "Normally, sunk cost traps players"
    
    text_long = "This is a very long sentence that has more than nine words to see if it truncates properly."
    phrase_long = extract_key_phrase(text_long)
    assert len(phrase_long.split()) == 9
    assert phrase_long == "This is a very long sentence that has more"

def test_build_drawtext_string():
    phrase = "Cookie Clicker: Ascension"
    out = build_drawtext_string(phrase)
    assert "drawbox=" in out
    assert "drawtext=" in out
    assert "text='Cookie Clicker\\: Ascension'" in out
    
    phrase_empty = ""
    assert build_drawtext_string(phrase_empty) == ""

def test_build_pollinations_prompt():
    # Case: Game + Moment
    out = build_pollinations_prompt("Cookie Clicker", None, "ascension reset")
    assert out == "Cookie Clicker ascension reset digital art, vibrant game UI screenshot style, 4K"
    
    # Case: Mechanic + Moment
    out = build_pollinations_prompt(None, "prestige", "climbing a mountain")
    assert out == "prestige climbing a mountain concept art, dark mode digital illustration, 4K"
    
    # Case: Fallback
    out = build_pollinations_prompt(None, None, None)
    assert "video game design concept art" in out

def test_build_infographic_prompt():
    text = "Players on r/incremental_games describe the emotional arc in four stages. It starts with joy."
    out = build_infographic_prompt(text)
    assert "Minimalist clean infographic style illustration representing" in out
    assert "Players on r/incremental_games describe the emotional arc in four stages" in out

if __name__ == "__main__":
    # Simple manual run
    test_extract_key_phrase()
    test_build_drawtext_string()
    test_build_pollinations_prompt()
    test_build_infographic_prompt()
    print("✓ All prompt_builder tests passed!")

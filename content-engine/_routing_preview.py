import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

# Extract the logic to just see what the query would be
from core.mechanic_extractor import extract as extract_mechanic

def preview():
    # Segments requested
    segments = [
        {"segment_index": 0, "game_title": "Cookie Clicker", "mechanic": "prestige_reset", "moment": "ascension button press", "text": "You just spent three hours building an empire..."},
        {"segment_index": 6, "game_title": "Cookie Clicker", "mechanic": "prestige_reset", "moment": "ascension upgrade tree", "text": "But the real depth is in the prestige tree..."},
        {"segment_index": 12, "game_title": "Adventure Capitalist", "mechanic": "prestige_reset", "moment": "angel investor multiplier unlock", "text": "Adventure Capitalist takes a different approach..."},
        {"segment_index": 13, "game_title": "Adventure Capitalist", "mechanic": "prestige_reset", "moment": "resetting for angels", "text": "When you reset, you gain angel investors..."}
    ]

    print("\n" + "="*80)
    print("ASSET ROUTING PREVIEW — DIRECTIVE GATE")
    print("="*80)
    print(f"| {'Seg':<3} | {'Game Title':<20} | {'Mechanic':<15} | {'Decision':<10} | {'Search Query Attempted':<35} |")
    print("|" + "-"*5 + "|" + "-"*22 + "|" + "-"*17 + "|" + "-"*12 + "|" + "-"*37 + "|")

    for seg in segments:
        # Priority check
        # 1. YouTube query generation (we assume local is empty for preview)
        # Use mechanic_extractor logic as per youtube_sourcer
        # (Mocking the extractor call to see what queries it produces)
        extracted = extract_mechanic(seg["text"])
        base_queries = extracted.get("search_queries", [])
        
        # If segments already have mec/mom, we can infer the query:
        query = f"{seg['game_title']} {seg['moment']} gameplay"
        if base_queries:
            query = base_queries[0]
            
        print(f"| {seg['segment_index']:<3} | {seg['game_title']:<20} | {seg['mechanic']:<15} | {'YouTube':<10} | {query:<35} |")

    print("="*80)
    print("STATUS: Pexels Disabled | Multi-modal Grounding Removed | Real-First Routing Active")
    print("="*80)

if __name__ == "__main__":
    preview()
unlink

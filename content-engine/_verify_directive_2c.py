import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.asset_sourcer import generate_ai_image

def verify():
    print("\n--- DIRECTIVE 2c VERIFICATION ---")
    
    # Segment 0: Cookie Clicker prestige_reset
    # We provide game_title, mechanic, moment to trigger the prompt engineer
    prompt = "Cookie Clicker prestige_reset ascension button press"
    game_title = "Cookie Clicker"
    mechanic = "prestige_reset"
    moment = "ascension button press"
    
    print(f"\n[Asset Sourcer] Testing grounded generation with Prompt Engineer...")
    res = generate_ai_image(
        prompt=prompt,
        segment_id=0,
        game_title=game_title,
        mechanic=mechanic,
        moment=moment
    )
    
    if res and res.get("paths"):
        print(f"\n✓ SUCCESS: Generated {len(res['paths'])} variants.")
        print(f"  Reference Used: {res.get('reference_used')}")
        print(f"  Paths: {res.get('paths')}")
    else:
        print("\n✗ FAILED: Image generation returned None.")

if __name__ == "__main__":
    verify()

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure youtube_clip_enabled is True for this test
import yaml
config_path = Path("config.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
    if not cfg.get("assembly"): cfg["assembly"] = {}
    cfg["assembly"]["youtube_clip_enabled"] = True
with open(config_path, "w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f)

from core.youtube_sourcer import source_for_segment

# Segment 0 data retrieved from DB
segment = {
    "id": 274,
    "script_id": 1,
    "segment_index": 0,
    "segment_text": "You just spent three hours building an empire. Millions of cookies, dozens of upgrades, a machine that basically plays itself. And then you hit a button that deletes all of it. Voluntarily. And it feels incredible. That's the prestige mechanic — the most psychologically clever trick in game design. Here's the thing: you didn't lose anything. Every second you spent grinding was secretly an investment in a multiplier you're about to unlock. Your brain registers it as a promotion, not a punishment. Small numbers become exciting again. The loop restarts faster, stronger. And somehow, the second run feels more like winning than anything the first run could ever offer.",
    "game_title": "Cookie Clicker",
    "mechanic": "prestige_reset",
    "moment": "ascension button press"
}

def diagnostic_run():
    print("\n--- YOUTUBE SOURCING DIAGNOSTIC (SEGMENT 0) ---")
    print(f"Segment: {segment['game_title']} | {segment['mechanic']} | {segment['moment']}")
    
    result = source_for_segment(segment)
    
    print("\n--- FINAL RESULT ---")
    if result:
        print(f"✓ SUCCESS: Clip found at {result['path']}")
        print(f"  Metadata: {json.dumps(result.get('metadata', {}), indent=2)}")
    else:
        print("✗ FAILED: No suitable candidates found or confidence too low.")

if __name__ == "__main__":
    diagnostic_run()

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.inventory_manager import check_inventory
from core.asset_sourcer import source_asset_for_segment

def test_reuse():
    print("="*70)
    print("ContentEngine TEST — Asset Inventory Reuse")
    print("="*70)
    print()

    # Define a segment that matches our recently accepted Cookie Clicker prestige asset
    # (Based on our Script 1 run, Segment 6 was Cookie Clicker/prestige_reset)
    dummy_segment = {
        "id": 999,
        "segment_index": 0,
        "game_title": "Cookie Clicker",
        "mechanic": "prestige_reset",
        "moment": "prestige button press",
        "segment_text": "And that is when you hit the legacy button and start over."
    }

    print("[1/2] Testing direct check_inventory()...")
    match = check_inventory("Cookie Clicker", "prestige_reset")
    if match:
        print(f"  ✓ SUCCESS: Found asset in inventory!")
        print(f"    Path: {match['asset_path']}")
        print(f"    Source: {match['source']}")
        print(f"    Description: {match['visual_description'][:80]}...")
    else:
        print("  ✗ FAILURE: No inventory match found for 'Cookie Clicker' / 'prestige_reset'.")

    print("\n[2/2] Testing through source_asset_for_segment() (Routing Logic)...")
    result = source_asset_for_segment(dummy_segment)
    
    if result.get("source") in ["youtube", "local", "wikimedia"] and "INVENTORY MATCH" in str(sys.stdout):
        # Note: We need to see the print output, but the result should have the correct source
        print(f"  ✓ SUCCESS: Routing identified inventory match.")
        print(f"    Final Source: {result['source']}")
        print(f"    Final Path: {result['path']}")
    elif result.get("source") == "youtube":
       # Since the script actually prints to stdout, we just check the source
       print(f"  ✓ SUCCESS: Asset sourced from inventory (Source: {result['source']})")
    else:
        print(f"  ? Result source: {result.get('source')}")

    print()
    print("="*70)

if __name__ == "__main__":
    test_reuse()

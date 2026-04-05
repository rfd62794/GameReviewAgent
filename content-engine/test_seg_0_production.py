import sys
import os
import sqlite3
import shutil
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.assembler import preprocess_segment
from core.db import get_connection

# Configure logging to see the FFmpeg errors if they happen
logging.basicConfig(level=logging.INFO)

def test_seg_0():
    print("="*70)
    print("ContentEngine TEST — Segment 0 Two-Pass Render")
    print("="*70)
    print()

    # 1. Setup paths
    engine_root = Path(__file__).resolve().parent
    temp_dir = engine_root / "temp_test"
    if temp_dir.exists(): shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    
    # 2. Mock config
    config = {
        "image_cycling_enabled": True,
        "image_cycling_interval_s": 12,
        "image_cycling_mode": "ken_burns"
    }

    # 3. Fetch real data from DB
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM asset_briefs WHERE script_id=1 AND segment_index=0").fetchone()
    conn.close()
    
    if not row:
        print("  ✗ FAILURE: Could not find Script 1 Segment 0 in database.")
        return

    segment_data = dict(row)
    print(f"  [Input] Segment Index: {segment_data['segment_index']}")
    print(f"  [Input] Duration:      {segment_data['estimated_duration_s']}s")
    print(f"  [Input] Asset:         {Path(segment_data['selected_asset']).name}")
    print(f"  [Input] Text:          {segment_data.get('drawtext_string', 'None')}")
    print()

    # 4. Run Preprocess
    print("[1/2] Executing preprocess_segment (Two-Pass Mode)...")
    try:
        out_file = preprocess_segment(segment_data, temp_dir, config)
        
        if out_file and out_file.exists():
            print(f"\n  ✓ SUCCESS: Segment 0 rendered!")
            print(f"    Output:    {out_file.name}")
            print(f"    File Size: {out_file.stat().st_size / 1024 / 1024:.2f} MB")
        else:
            print(f"\n  ✗ FAILURE: Output file not found or None returned.")
            
    except Exception as e:
        print(f"\n  ✗ CRASH: {str(e)}")

    print("\n" + "="*70)

if __name__ == "__main__":
    test_seg_0()

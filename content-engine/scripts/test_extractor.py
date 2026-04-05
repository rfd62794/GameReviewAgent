import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from core.db import get_connection
from core.mechanic_extractor import extract

def test_extractor():
    conn = get_connection()
    # E2E test is using SCRIPT_ID = 1 based on run_p3b.py
    cursor = conn.execute("SELECT segment_text FROM asset_briefs WHERE script_id = 1 ORDER BY segment_index ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        print("No segment found!")
        return

    segment_text = row[0]
    print("--- SEGMENT 0 TEXT (HOOK) ---")
    print(segment_text)
    print("-----------------------------\n")

    print("[1] Executing LLM Extractor...")
    result = extract(segment_text)
    
    print("\n--- RAW JSON EXTRACTOR OUTPUT ---")
    print(json.dumps(result, indent=2))
    print("---------------------------------")

if __name__ == "__main__":
    test_extractor()

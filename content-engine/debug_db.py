import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.db import get_connection

def main():
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    rows = conn.execute(
        "SELECT segment_index, asset_source, review_status, review_reason, review_confidence FROM asset_briefs WHERE script_id=1 AND segment_index IN (0, 2, 12)"
    ).fetchall()
    
    print("\nDEBUG RETRY RESULTS (0, 2, 12):")
    if not rows:
        print("  None found.")
    for r in rows:
        print(f"Seg {r['segment_index']}: Source={r['asset_source']} Status={r['review_status']} Conf={r['review_confidence']}")
        print(f"  Reason: {r['review_reason']}")
        
    conn.close()

if __name__ == "__main__":
    main()

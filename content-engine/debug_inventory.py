import sys
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection

def main():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    print("\n--- ASSET INVENTORY DUMP (Accepted Only) ---")
    rows = conn.execute(
        "SELECT game_title, mechanic, review_status, asset_path FROM asset_inventory WHERE review_status='accepted'"
    ).fetchall()
    
    if not rows:
        print("  Inventory is empty!")
    for r in rows:
        print(f"  - {r['game_title']} | {r['mechanic']} | {r['review_status']} | {Path(r['asset_path']).name}")
        
    print("\n--- ASSET INVENTORY DUMP (Rejected/Pending) ---")
    rows = conn.execute(
        "SELECT game_title, mechanic, review_status, asset_path FROM asset_inventory WHERE review_status != 'accepted'"
    ).fetchall()
    for r in rows:
        print(f"  - {r['game_title']} | {r['mechanic']} | {r['review_status']} | {Path(r['asset_path']).name}")
        
    conn.close()

if __name__ == "__main__":
    main()

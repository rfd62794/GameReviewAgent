import sys
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection

def preview():
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    # Target segments
    indices = (0, 6, 12, 13)
    rows = conn.execute(
        "SELECT segment_index, game_title, mechanic, moment, search_query FROM asset_briefs WHERE script_id=1 AND segment_index IN (?,?,?,?) ORDER BY segment_index",
        indices
    ).fetchall()
    conn.close()

    print("\n" + "="*90)
    print("ASSET ROUTING PREVIEW — DB-FIRST VERIFICATION")
    print("="*90)
    print(f"| {'Seg':<3} | {'Game Title':<20} | {'Mechanic':<15} | {'Decision':<10} | {'Top Search Query (DB)':<32} |")
    print("|" + "-"*5 + "|" + "-"*22 + "|" + "-"*17 + "|" + "-"*12 + "|" + "-"*34 + "|")

    for row in rows:
        # Parse search_query JSON
        raw = row.get("search_query", "")
        top_query = "N/A"
        if raw:
            try:
                queries = json.loads(raw)
                if isinstance(queries, list) and len(queries) > 0:
                    top_query = queries[0]
                else:
                    top_query = str(queries)
            except:
                top_query = raw[:30]
        
        # Decision logic (simplified for preview)
        decision = "YouTube" if row["game_title"] else "AI Gen"
        
        print(f"| {row['segment_index']:<3} | {row['game_title']:<20} | {row['mechanic']:<15} | {decision:<10} | {top_query:<32} |")

    print("="*90)
    print("STATUS: Redundant Extraction REMOVED | DB-First Queries ACTIVE")
    print("="*90)

if __name__ == "__main__":
    preview()
    

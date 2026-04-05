import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import get_connection
from core.youtube_sourcer import (
    search, 
    fetch_transcript, 
    judge_relevance, 
    find_transcript_window,
    download_clip
)

def test_segment_0():
    print("="*60)
    print("TESTING SEGMENT 0 (HOOK) LIVE")
    print("="*60)
    
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    seg_cursor = conn.execute("SELECT * FROM asset_briefs WHERE segment_index = 0 AND script_id = 1 LIMIT 1")
    segment = seg_cursor.fetchone()
    conn.close()

    if not segment:
        print("Segment 0 not found!")
        return

    query = segment.get("youtube_search_query", segment.get("search_query"))
    print(f"\n[1] Generated YouTube Search Query:\n    {query}")
    
    print("\n[2] Fetching 5 Candidate Titles...")
    candidates = search(query, n=5)
    for idx, c in enumerate(candidates, 1):
        print(f"    {idx}. {c.get('title')} ({c.get('channel')})")
        
    if not candidates:
        print("    No candidates found via yt-dlp.")
        return

    print("\n[3] Evaluating best candidate transcript (using first candidate for test log)...")
    
    best_candidate = None
    highest_conf = 0.0
    detailed_log = ""
    
    for idx, cand in enumerate(candidates, 1):
        transcript = fetch_transcript(cand.get("url", ""))
        if not transcript:
            continue
            
        keywords = query.split()
        window = find_transcript_window(transcript, keywords)
        
        # We only want to log the first one we check for review purposes
        if idx == 1:
            print("--- TRANSCRIPT EXCERPT WINDOW FOR TOP CANDIDATE ---")
            print(window[:1000] + "\n...[truncated]")
            print("---------------------------------------------------")
        
        judgment = judge_relevance(segment.get("segment_text", ""), cand, transcript, keywords)
        conf = judgment.get("confidence", 0.0)
        
        if idx == 1:
            print("\n[4] Raw LLM Judgment JSON (Candidate 1):")
            print(json.dumps(judgment, indent=2))
        
        if conf >= 0.8:
            best_candidate = {**cand, **judgment}
            break
        elif conf > highest_conf:
            highest_conf = conf
            best_candidate = {**cand, **judgment}

    print("\n[5] Final Threshold Evaluation:")
    if best_candidate and best_candidate.get("confidence", 0.0) >= 0.8:
        print(f"    ACCEPTED: '{best_candidate.get('title')}' with confidence {best_candidate.get('confidence')}")
        print("    --> Action: Downloading clip...")
        clip_path = download_clip(
            url=best_candidate.get("url"),
            start=best_candidate.get("timestamp_start", 0),
            end=best_candidate.get("timestamp_end", 10),
            buffer=2
        )
        print(f"    --> Download complete: {clip_path}")
    else:
        conf = best_candidate.get("confidence", 0.0) if best_candidate else 0.0
        print(f"    REJECTED: Highest confidence was {conf} (< 0.8 threshold)")
        print("    --> Action: Fall back to Pollinations.ai")

if __name__ == "__main__":
    test_segment_0()

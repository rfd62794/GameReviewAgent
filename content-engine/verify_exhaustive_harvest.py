import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.youtube_sourcer import fetch_transcript, judge_relevance

def live_verification():
    print("="*70)
    print("ContentEngine LIVE VERIFICATION — Exhaustive Harvest (SDD v0.6)")
    print("="*70)
    print()

    video_url = "https://www.youtube.com/watch?v=8eA1hZgBhVI"
    video_id = "8eA1hZgBhVI"
    
    # Segment to illustrate (Cookie Clicker Ascension)
    segment_text = (
        "Cookie Clicker's prestige reset system is the engine that drives its multi-year progression. "
        "When you hit that legacy button, you're not just starting over — you're ascending with "
        "heavenly chips that multiply your future gains."
    )
    
    candidate = {
        "id": video_id,
        "title": "Cookie Clicker - First, Second and Third Ascension Guide",
        "channel": "Cookie Smash",
        "url": video_url
    }
    
    print(f"[1/3] Fetching full transcript for {video_id} (timeout=300s)...")
    transcript = fetch_transcript(video_url, timeout=300)
    
    if not transcript:
        print("  ✗ FAILURE: Could not fetch transcript.")
        return

    print(f"  ✓ SUCCESS: Fetched {len(transcript)} transcript lines.")

    print(f"\n[2/3] Running multi-segment LLM Judge (Exhaustive Harvest Mode)...")
    keywords = ["ascension", "prestige", "heavenly", "chips", "reset", "legacy"]
    
    judgment = judge_relevance(segment_text, candidate, transcript, keywords)
    
    if not judgment.get("video_relevant"):
        print("  ✗ FAILURE: LLM judged video as not relevant.")
        return

    segments = judgment.get("segments", [])
    print(f"\n[3/3] HARVEST RESULTS:")
    print(f"  Total Segments Found: {len(segments)}")
    print(f"  ------------------------------------------------")
    
    for i, s in enumerate(segments):
        print(f"  Segment {i+1}:")
        print(f"    - Mechanic:  {s['mechanic_shown']}")
        print(f"    - Range:     {s['timestamp_start']}s - {s['timestamp_end']}s")
        print(f"    - Confidence: {s['confidence']}")
        print(f"    - Reason:    {s['reason']}")
        print()

    if len(segments) >= 3:
        print("✓ SUCCESS: Identified 3+ relevant segments covering multiple mechanics.")
    else:
        print(f"? Total segments: {len(segments)}. Check if deduplication was too aggressive.")

    print("\n" + "="*70)

if __name__ == "__main__":
    live_verification()

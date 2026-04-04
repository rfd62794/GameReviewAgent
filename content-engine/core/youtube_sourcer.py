import subprocess
import json
import logging
import re
import tempfile
from pathlib import Path
from typing import List, Dict

from core.llm_client import create_llm_client as get_llm_client
from core.mechanic_extractor import extract as extract_mechanic
from core.index_manager import lookup, record_attempt, record_success

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CLIPS_DIR = ASSETS_DIR / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)


def search(query: str, n: int = 5) -> list[dict]:
    """Retrieve top N video candidates using yt-dlp."""
    # Example yt-dlp command to grab N results in JSON
    # yt-dlp "ytsearch5:query" --dump-json --flat-playlist
    cmd = [
        "yt-dlp",
        f"ytsearch{n}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--ignore-errors"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        candidates = []
        for line in res.stdout.strip().split("\n"):
            if not line: continue
            data = json.loads(line)
            candidates.append({
                "id": data.get("id"),
                "title": data.get("title"),
                "channel": data.get("uploader"),
                "duration": data.get("duration"),
                "url": data.get("url")
            })
        return candidates
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp search error: {e}")
        return []


def vtt_to_text(vtt_path: Path) -> List[Dict]:
    """Parse VTT to plain text with timestamps."""
    transcript = []
    try:
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        print("\n--- RAW VTT HEAD (20 lines) ---")
        for debug_line in lines[:20]:
            print(debug_line.strip())
        print("-------------------------------\n")
        
        current_time = 0
        for line in lines:
            line = line.strip()
            if not line or line == "WEBVTT" or "Kind:" in line or "Language:" in line:
                continue
            
            # Match timestamp line (e.g. 00:00:00.000 --> 00:00:02.000 or 00:00.000)
            if "-->" in line:
                start_str = line.split("-->")[0].strip()
                parts = start_str.split(":")
                try:
                    if len(parts) == 3:
                        h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                        current_time = int(h * 3600 + m * 60 + s)
                    elif len(parts) == 2:
                        m, s = int(parts[0]), float(parts[1])
                        current_time = int(m * 60 + s)
                except ValueError:
                    pass
                continue
                
            text = re.sub(r'<[^>]+>', '', line).strip()
            if text and not text.isdigit():
                if transcript and transcript[-1]["text"] == text:
                    continue
                transcript.append({"timestamp_s": current_time, "text": text})
                
        return transcript
    except Exception as e:
        logger.error(f"Failed to parse VTT: {e}")
        return []


def fetch_transcript(url: str, timeout: int = 15) -> List[Dict] | None:
    """Fetch auto-generated captions/subtitles via VTT."""
    with tempfile.TemporaryDirectory() as tempdir:
        temp_path = Path(tempdir)
        cmd = [
            "yt-dlp",
            "--js-runtimes", f"nodejs:{Path('node.exe').absolute()}",
            "--write-auto-subs",
            "--sub-langs", "en",
            "--skip-download",
            "-o", f"{temp_path}/%(id)s",
            url
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                vtt_files = list(temp_path.glob("*.vtt"))
                if vtt_files:
                    return vtt_to_text(vtt_files[0])
            else:
                logger.warning(f"Failed to fetch transcript: {res.stderr[:200]}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Transcript fetch timed out for {url}")
            return None
        except Exception as e:
            logger.error(f"Transcript fetch error: {e}")
            return None


def find_transcript_window(transcript: List[Dict], keywords: list[str]) -> str:
    """Find the transcript segment centered around keyword occurrences returning formatted string."""
    best_idx = -1
    
    for i, entry in enumerate(transcript):
        text_lower = entry["text"].lower()
        if any(kw.lower() in text_lower for kw in keywords if len(kw) > 3):
            best_idx = i
            break
            
    if best_idx == -1:
        best_idx = 0
        
    start_idx = max(0, best_idx - 15)
    end_idx = min(len(transcript), best_idx + 15)
    
    window_lines = []
    for entry in transcript[start_idx:end_idx]:
        window_lines.append(f"[{entry['timestamp_s']}s] {entry['text']}")
        
    return "\n".join(window_lines)


def judge_relevance(segment_text: str, candidate: dict, transcript: List[Dict], keywords: list[str]) -> dict:
    """Ask LLM to judge sequence relevance based on transcript."""
    # Load prompt contract
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "clip_relevance.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()
    except FileNotFoundError:
        logger.error("Clip relevance prompt contract not found.")
        return {"relevant": False, "confidence": 0.0}

    excerpt = find_transcript_window(transcript, keywords)

    # Format prompt by replacing placeholders (avoids curly brace clashes with JSON schema in prompt)
    formatted = sys_prompt.replace("{segment_text}", segment_text)
    formatted = formatted.replace("{video_title}", candidate.get("title", ""))
    formatted = formatted.replace("{channel}", candidate.get("channel", ""))
    formatted = formatted.replace("{transcript_excerpt}", excerpt)

    client = get_llm_client(model="deepseek/deepseek-chat")
    try:
        response_dict = client.generate(
            system_prompt="You evaluate YouTube transcript excerpts against a strict JSON schema.",
            prompt=formatted,
            temperature=0.0
        )
        response_text = response_dict.get("text", "")
        
        # Strip code fences if present
        cleaned = re.sub(r'```json|```', '', response_text).strip()
        # Find outermost JSON object
        # Note: robust match for JSON object structure, avoiding generic text
        match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
        if not match:
            logger.error("No JSON object found in LLM response")
            return {"relevant": False, "confidence": 0.0}
        return json.loads(match.group())
    except Exception as e:
        logger.error(f"LLM judgment failed: {e}")
        return {"relevant": False, "confidence": 0.0}


def download_clip(url: str, start: int, end: int, buffer: int = 2) -> Path | None:
    """Download a targeted section of the video using yt-dlp."""
    s = max(0, start - buffer)
    e = end + buffer
    video_id = url.split("=")[-1]
    out_path = CLIPS_DIR / f"{video_id}_{s}_{e}.mp4"
    
    cmd = [
        "yt-dlp",
        "--js-runtimes", f"nodejs:{Path('node.exe').absolute()}",
        "--download-sections", f"*{s}-{e}",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", str(out_path),
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"yt-dlp download failed: {result.stderr[:500]}")
            return None
        if out_path.exists():
            return out_path
        return None
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp download timed out")
        return None


def source_for_segment(segment: dict) -> dict | None:
    """Full P4 YouTube sourcing flow per SDD v0.4."""
    segment_text = segment.get("segment_text", "")
    if not segment_text:
        return None

    # a) Call mechanic_extractor
    extracted = extract_mechanic(segment_text)
    games = extracted.get("games", [])
    mechanic = extracted.get("mechanic", "unknown")
    
    # Base queries from the LLM extractor
    base_queries = extracted.get("search_queries", [])
    if not base_queries:
        # Fallback if extraction totally failed
        fallback_query = segment.get("youtube_search_query", segment.get("search_query", "idle game gameplay"))
        base_queries = [fallback_query]

    # b) Index Lookup
    search_queries = []
    for game in games:
        indexed_queries = lookup(game, mechanic)
        for iq in indexed_queries:
            if iq not in search_queries:
                search_queries.append(iq)
    
    # Append the newly generated LLM base queries
    for bq in base_queries:
        if bq not in search_queries:
            search_queries.append(bq)
            
    # Short circuit check
    if not search_queries:
        return None

    # ---- Added TRACE PRINTS ----
    print(f"\n================ SEGMENT {segment.get('segment_index', '?')} ================")
    words = segment_text.split()
    print(f"TEXT: {' '.join(words[:20])}...")
    print(f"EXTRACTOR: Game: {games} | Mechanic: {mechanic} | Moment: {extracted.get('moment')}")
    print(f"QUERIES: {search_queries[:2]}")

    # We evaluate sequentially across top queries until a hit.
    best_candidate = None
    highest_conf = 0.0
    
    # Try the top query first (or could iterate safely, but let's stick to simple logic: top query gets candidates)
    
    # Limit number of queries to search to avoid exploding yt-dlp calls
    for query in search_queries[:2]:
        if best_candidate and best_candidate.get("confidence", 0.0) >= 0.8:
            break
            
        candidates = search(query, n=5)
        for cand in candidates:
            transcript = fetch_transcript(cand.get("url", ""))
            if not transcript:
                continue
                
            keywords = query.split()
            judgment = judge_relevance(segment_text, cand, transcript, keywords)
            conf = judgment.get("confidence", 0.0)
            
            print(f"  ? CANDIDATE: '{cand.get('title')}' -> Confidence: {conf}")
            
            # c) Record attempt
            top_game = games[0] if games else "unknown"
            record_attempt(top_game, mechanic, query, cand.get("channel"))
            
            if conf >= 0.8:
                best_candidate = {**cand, **judgment}
                best_candidate["_query"] = query
                break
            elif conf > highest_conf:
                highest_conf = conf
                best_candidate = {**cand, **judgment}
                best_candidate["_query"] = query

    if best_candidate and best_candidate.get("confidence", 0.0) >= 0.8:
        print(f"  ---> ACCEPTED: {best_candidate.get('title')} (Conf: {best_candidate.get('confidence')})")
        # d) On acceptance
        top_game = games[0] if games else "unknown"
        record_success(
            game_title=top_game,
            mechanic=mechanic,
            query=best_candidate["_query"],
            channel=best_candidate.get("channel"),
            confidence=best_candidate.get("confidence"),
            segment_text=segment_text
        )
        
        clip_path = download_clip(
            url=best_candidate.get("url"),
            start=best_candidate.get("timestamp_start", 0),
            end=best_candidate.get("timestamp_end", 10),
            buffer=2
        )
        if clip_path:
            return {
                "path": str(clip_path),
                "source": "youtube",
                "metadata": best_candidate
            }
            
    # e) On all candidates rejected -> Pollinations fallback natively happens upstream if None returned
    print(f"  ---> REJECTED ALL CANDIDATES. Falling back upstream.")
    return None

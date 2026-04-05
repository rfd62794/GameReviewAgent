import subprocess
import json
import yaml
import logging
import re
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from core.llm_client import create_llm_client as get_llm_client
from core.mechanic_extractor import extract as extract_mechanic
from core.index_manager import lookup, record_attempt, record_success, boost_video_segments

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
CLIPS_DIR = ASSETS_DIR / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)
        YTDLP_FLAGS = _config.get("ytdlp_extra_flags", [])
except Exception as e:
    logger.warning(f"Failed to load config.yaml for yt-dlp: {e}")
    YTDLP_FLAGS = []


def search(query: str, n: int = 5) -> list[dict]:
    """Retrieve top N video candidates using yt-dlp."""
    # Example yt-dlp command to grab N results in JSON
    # yt-dlp "ytsearch5:query" --dump-json --flat-playlist
    cmd = [
        "yt-dlp",
        "--js-runtimes", f"node:{Path('node.exe').absolute()}"
    ] + YTDLP_FLAGS + [
        "ytsearch" + str(n) + ":" + query,
        "--dump-json",
        "--default-search", "ytsearch",
        "--no-playlist",
        "--match-filter", "duration < 1200 & duration > 60",
        "--reject-title", "shorts|tiktok"
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
                "url": data.get("webpage_url") or data.get("url")
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


def fetch_transcript(url: str, timeout: int = 300) -> List[Dict] | None:
    """Fetch auto-generated captions/subtitles via VTT."""
    with tempfile.TemporaryDirectory() as tempdir:
        temp_path = Path(tempdir)
        cmd = [
            "yt-dlp",
            "--js-runtimes", f"node:{Path('node.exe').absolute()}"
        ] + YTDLP_FLAGS + [
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


def chunk_transcript(transcript: List[Dict], chunk_size: int = 4000, overlap: int = 500) -> List[str]:
    """Split transcript into overlapping chunks of words/lines for LLM processing."""
    if not transcript:
        return []

    lines = [f"[{entry['timestamp_s']}s] {entry['text']}" for entry in transcript]
    
    # Simple word-count based chunking
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for line in lines:
        words = line.split()
        if current_word_count + len(words) > chunk_size:
            chunks.append("\n".join(current_chunk))
            # Start next chunk with overlap
            # For simplicity, we just keep the last 20 lines as overlap
            current_chunk = current_chunk[-20:] + [line]
            current_word_count = sum(len(l.split()) for l in current_chunk)
        else:
            current_chunk.append(line)
            current_word_count += len(words)
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks


def merge_overlapping_segments(segments: List[Dict]) -> List[Dict]:
    """
    Deduplication rule for judge_relevance() output.
    Sort by timestamp_start and merge segments with >50% overlap of the same mechanic.
    """
    if not segments:
        return []
        
    # Sort by mechanic then by start time
    segments.sort(key=lambda x: (x.get("mechanic_shown", ""), x.get("timestamp_start", 0)))
    
    merged_all = []
    if not segments: return []
    
    curr = segments[0]
    for next_seg in segments[1:]:
        if curr.get("mechanic_shown") == next_seg.get("mechanic_shown"):
            # Same mechanic, check overlap
            overlap = min(curr["timestamp_end"], next_seg["timestamp_end"]) - max(curr["timestamp_start"], next_seg["timestamp_start"])
            shorter = min(curr["timestamp_end"] - curr["timestamp_start"], next_seg["timestamp_end"] - next_seg["timestamp_start"])
            
            if shorter > 0 and (overlap / shorter) > 0.5:
                # Merge
                curr = {
                    "timestamp_start": min(curr["timestamp_start"], next_seg["timestamp_start"]),
                    "timestamp_end": max(curr["timestamp_end"], next_seg["timestamp_end"]),
                    "confidence": max(curr["confidence"], next_seg["confidence"]),
                    "mechanic_shown": curr["mechanic_shown"],
                    "reason": curr["reason"] if curr["confidence"] >= next_seg["confidence"] else next_seg["reason"]
                }
            else:
                merged_all.append(curr)
                curr = next_seg
        else:
            merged_all.append(curr)
            curr = next_seg
            
    merged_all.append(curr)
    
    # Final sort by confidence DESC
    merged_all.sort(key=lambda x: x["confidence"], reverse=True)
    return merged_all


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
    """Ask LLM to judge sequence relevance based on FULL transcript using chunking."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "clip_relevance.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()
    except FileNotFoundError:
        logger.error("Clip relevance prompt contract not found.")
        return {"video_relevant": False, "segments": []}

    chunks = chunk_transcript(transcript)
    all_segments = []
    video_relevant = False

    client = get_llm_client(model="deepseek/deepseek-chat")
    
    for chunk in chunks:
        formatted = sys_prompt.replace("{segment_text}", segment_text)
        formatted = formatted.replace("{video_title}", candidate.get("title", ""))
        formatted = formatted.replace("{channel}", candidate.get("channel", ""))
        formatted = formatted.replace("{transcript_excerpt}", chunk)

        try:
            response_dict = client.generate(
                system_prompt="You evaluate YouTube transcripts. Returns strict JSON with 'video_relevant' and 'segments' array.",
                prompt=formatted,
                temperature=0.0
            )
            response_text = response_dict.get("text", "")
            cleaned = re.sub(r'```json|```', '', response_text).strip()
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if not match: continue
            
            judgment = json.loads(match.group())
            if judgment.get("video_relevant"):
                video_relevant = True
                segs = judgment.get("segments", [])
                # Only keep high confidence segments
                all_segments.extend([s for s in segs if s.get("confidence", 0) >= 0.8])
        except Exception as e:
            logger.error(f"LLM chunk judgment failed: {e}")

    # Merge overlapping segments
    final_segments = merge_overlapping_segments(all_segments)
    
    return {
        "video_relevant": video_relevant and len(final_segments) > 0,
        "segments": final_segments
    }


def download_clip(url: str, start: int, end: int, buffer: int = 2) -> Path | None:
    """Download a targeted section of the video using yt-dlp."""
    s = max(0, start - buffer)
    e = end + buffer
    video_id = url.split("=")[-1]
    out_path = CLIPS_DIR / f"{video_id}_{s}_{e}.mp4"
    
    cmd = [
        "yt-dlp",
        "--js-runtimes", f"node:{Path('node.exe').absolute()}"
    ] + YTDLP_FLAGS + [
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

    # a) Use pre-extracted queries from DB first
    # This prevents redundant LLM calls and stochastic drift
    raw = segment.get("search_query", "")
    queries = []
    if raw:
        try:
            queries = json.loads(raw)
            if not isinstance(queries, list):
                queries = [str(queries)]
        except (json.JSONDecodeError, TypeError):
            queries = [raw] if raw else []
    
    # b) Only call extractor if DB has no queries
    if not queries:
        extracted = extract_mechanic(segment_text)
        queries = extracted.get("search_queries", [])
    
    # Deduplicate preserving order
    seen = set()
    base_queries = []
    for q in queries:
        if q and q not in seen:
            base_queries.append(q)
            seen.add(q)

    # c) Index Lookup (Supplementary)
    games = segment.get("game_title", "")
    if isinstance(games, str): games = [games]
    mechanic = segment.get("mechanic", "unknown")
    
    search_queries = []
    for game in games:
        if not game: continue
        indexed_queries = lookup(game, mechanic)
        for iq in indexed_queries:
            if iq and iq not in seen:
                search_queries.append(iq)
                seen.add(iq)
    
    # Prepend the high-fidelity base queries
    search_queries = base_queries + search_queries
            
    # Short circuit check
    if not search_queries:
        return None

    # ---- Added TRACE PRINTS ----
    print(f"\n================ SEGMENT {segment.get('segment_index', '?')} ================")
    words = segment_text.split()
    print(f"TEXT: {' '.join(words[:20])}...")
    moment = segment.get("moment")
    if not moment and 'extracted' in locals():
        moment = extracted.get("moment")
    print(f"EXTRACTOR: Game: {games} | Mechanic: {mechanic} | Moment: {moment}")
    print(f"QUERIES: {search_queries[:2]}")

    # We evaluate sequentially across top queries until a hit.
    best_candidate = None
    all_found_segments = []
    
    # Limit number of queries to search
    for query in search_queries[:2]:
        if best_candidate:
            break
            
        candidates = search(query, n=5)
        for cand in candidates:
            url = cand.get("url")
            if not url: continue
                
            transcript = fetch_transcript(url)
            if not transcript: continue
                
            keywords = query.split()
            judgment = judge_relevance(segment_text, cand, transcript, keywords)
            
            if not judgment.get("video_relevant"):
                continue
                
            segments = judgment.get("segments", [])
            if not segments:
                continue
                
            print(f"  ? CANDIDATE: '{cand.get('title')}' -> Found {len(segments)} segments")
            for s in segments:
                print(f"    - {s['mechanic_shown']} at {s['timestamp_start']}s (Conf: {s['confidence']})")
            
            # --- PRIMARY SEGMENT SELECTION ---
            # We look for a segment that exactly matches the requested mechanic OR has highest confidence
            primary = None
            for s in segments:
                if s["mechanic_shown"] == mechanic:
                    primary = s
                    break
            if not primary:
                primary = segments[0] # Highest confidence
                
            # --- QUEUEING REMAINING SEGMENTS ---
            remaining = [s for s in segments if s != primary]
            if remaining:
                print(f"    [Queue] Adding {len(remaining)} segments to background download queue...")
                queue_segments(url, cand.get("id"), remaining, top_game)
            
            best_candidate = {**cand, **primary}
            best_candidate["_query"] = query
            break

    if best_candidate:
        conf = best_candidate.get("confidence", 0)
        print(f"  ---> ACCEPTED: {best_candidate.get('title')} (Conf: {conf})")
        
        # d) Record success
        top_game = games[0] if games else "unknown"
        record_success(
            game_title=top_game,
            mechanic=mechanic,
            query=best_candidate["_query"],
            channel=best_candidate.get("channel"),
            confidence=conf,
            segment_text=segment_text
        )
        
        # Boost segments from same video in queue
        boost_video_segments(best_candidate.get("id"))
        
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
            
    print(f"  ---> REJECTED ALL CANDIDATES. Falling back upstream.")
    return None


def queue_segments(url: str, video_id: str, segments: List[Dict], game_title: str):
    """Add segments to the background download queue."""
    conn = get_connection()
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    try:
        for s in segments:
            conn.execute("""
                INSERT INTO clip_download_queue (
                    youtube_url, youtube_video_id, timestamp_start, timestamp_end,
                    confidence, mechanic_shown, game_title, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?)
            """, (
                url, video_id, s["timestamp_start"], s["timestamp_end"],
                s["confidence"], s["mechanic_shown"], game_title, now
            ))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to queue segments: {e}")
    finally:
        conn.close()

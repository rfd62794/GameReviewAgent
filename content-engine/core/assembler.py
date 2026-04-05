import re
import subprocess
from pathlib import Path


def _extract_key_phrase(segment_text: str, max_words: int = 8) -> str:
    """Extract the first sentence truncated to max_words for the text overlay."""
    if not segment_text:
        return ""
    # Take first sentence
    sentence_match = re.split(r'(?<=[.!?])\s+', segment_text.strip())
    first = sentence_match[0].strip() if sentence_match else segment_text.strip()
    # Drop trailing punctuation
    first = first.rstrip(".!?,;:")
    words = first.split()
    if len(words) > max_words:
        first = " ".join(words[:max_words])
    return first


def _escape_drawtext(text: str) -> str:
    """Escape characters for FFmpeg drawtext filter."""
    # Escape backslash, colon, single-quote, and special chars
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def preprocess_segment(segment: dict, temp_dir: Path) -> Path | None:
    """
    Process an asset into a standardized 1920x1080 30fps MP4 segment.
    Applies Ken Burns effect for images.
    Adds drawtext overlay (key phrase, bottom-third, white text on semi-transparent bar).
    """
    asset_path = Path(segment["selected_asset"])
    duration = segment["estimated_duration_s"]
    vtype = segment["visual_type"]
    idx = segment["segment_index"]
    segment_text = segment.get("segment_text", "")

    out_file = temp_dir / f"seg_{idx}.mp4"

    # --- Key phrase extraction ---
    key_phrase = _extract_key_phrase(segment_text)
    escaped_phrase = _escape_drawtext(key_phrase)

    # drawtext filter: white text, bottom-third, semi-transparent black bar behind it
    # Bar: filled rectangle at y=810 (bottom third of 1080), full width
    # Text: fontsize 52, centered, at y=820
    drawtext_filter = (
        f"drawbox=x=0:y=810:w=iw:h=140:color=black@0.55:t=fill,"
        f"drawtext=text='{escaped_phrase}'"
        f":fontsize=52:fontcolor=white:x=(w-text_w)/2:y=840"
        f":shadowcolor=black@0.6:shadowx=2:shadowy=2"
    )

    print(f"  [DRAWTEXT seg {idx}] \"{key_phrase}\"")
    print(f"    filter: {drawtext_filter[:120]}{'...' if len(drawtext_filter) > 120 else ''}")

    # 1920x1080 format string
    filt_prefix = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"

    # Choose processing mode based on file extension (robust for MVP fallback)
    is_image = asset_path.suffix.lower() in [".jpg", ".jpeg", ".png"]
    
    cmd = ["ffmpeg", "-y"]
    
    if is_image:
        # Apply Ken Burns to images
        cmd.extend(["-loop", "1", "-i", str(asset_path)])
        frames = duration * 30
        kb_filter = (
            f"{filt_prefix},"
            f"zoompan=z='min(zoom+0.0015,1.5)':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080,"
            f"{drawtext_filter}"
        )
        cmd.extend(["-vf", kb_filter])
        cmd.extend(["-t", str(duration)])
    else:
        # Standard video + drawtext
        cmd.extend(["-i", str(asset_path)])
        cmd.extend(["-vf", f"{filt_prefix},fps=30,{drawtext_filter}"])
        cmd.extend(["-t", str(duration)])

    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-an", str(out_file)])

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_file
    except subprocess.CalledProcessError as e:
        print(f"Error processing segment {idx}: {e}")
        return None


def assemble_video(segments: list[dict], audio_path: Path, output_path: Path, temp_dir: Path):
    """
    Concatenate preprocessed segments and mux with audio.
    """
    concat_file = temp_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg['temp_file']}'\n")
            
    # Concatenate visuals
    visuals_only = temp_dir / "visuals_no_audio.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-c", "copy", str(visuals_only)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Mux with audio
    subprocess.run([
        "ffmpeg", "-y", "-i", str(visuals_only), "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac", "-shortest", str(output_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

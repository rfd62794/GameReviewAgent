import re
import subprocess
from pathlib import Path


# Pure internal functions moved to core/prompt_builder.py


def preprocess_segment(segment: dict, temp_dir: Path, drawtext_filter: str) -> Path | None:
    """
    Process an asset into a standardized 1920x1080 30fps MP4 segment.
    Applies Ken Burns effect for images.
    Uses the provided drawtext_filter for text overlays.
    """
    asset_path = Path(segment["selected_asset"])
    duration = segment["estimated_duration_s"]
    vtype = segment["visual_type"]
    idx = segment["segment_index"]

    out_file = temp_dir / f"seg_{idx}.mp4"

    # NOTE: drawtext_filter is now received from stage_p7_assemble.py
    # which reads it from the database (built by stage_p4b_source.py).
    
    if drawtext_filter:
        print(f"  [ASSEMBLER seg {idx}] Applying drawtext overlay...")
    else:
        print(f"  [ASSEMBLER seg {idx}] No drawtext overlay.")

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

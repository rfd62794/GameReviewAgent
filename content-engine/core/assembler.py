import subprocess
from pathlib import Path

def preprocess_segment(segment: dict, temp_dir: Path) -> Path | None:
    """
    Process an asset into a standardized 1920x1080 30fps MP4 segment.
    Applies Ken Burns effect for images.
    """
    asset_path = Path(segment["selected_asset"])
    duration = segment["estimated_duration_s"]
    vtype = segment["visual_type"]
    idx = segment["segment_index"]
    
    out_file = temp_dir / f"seg_{idx}.mp4"
    
    # 1920x1080 format string
    filt_prefix = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
    
    cmd = ["ffmpeg", "-y"]
    
    if vtype in ["stock_still", "ai_image"]:
        # Apply Ken Burns to images
        cmd.extend(["-loop", "1", "-i", str(asset_path)])
        frames = duration * 30
        filt = f"{filt_prefix},zoompan=z='min(zoom+0.0015,1.5)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080"
        cmd.extend(["-vf", filt])
        cmd.extend(["-t", str(duration)])
    else:
        # Standard video
        cmd.extend(["-i", str(asset_path)])
        # Slow down / loop video if it's too short, or just trim
        # Minimal viable product: just trim and scale
        cmd.extend(["-vf", f"{filt_prefix},fps=30"])
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

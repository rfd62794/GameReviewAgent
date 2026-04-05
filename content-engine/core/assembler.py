import re
import subprocess
import json
import math
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import whisper
except ImportError:
    whisper = None


def generate_srt(audio_path: Path, output_srt_path: Path):
    """
    Generate an SRT file using Whisper transcription with word-level timestamps.
    """
    if not whisper:
        print("  [WHISPER] Subtitle generation skipped: whisper not installed.")
        return None
        
    print(f"  [WHISPER] Transcribing {audio_path.name}...")
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en")
    
    with open(output_srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result["segments"], 1):
            start = _format_timestamp(segment["start"])
            end = _format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
            
    print(f"      ✓ SRT generated: {output_srt_path.name}")
    return output_srt_path


def _format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm string."""
    td_h = int(seconds // 3600)
    td_m = int((seconds % 3600) // 60)
    td_s = int(seconds % 60)
    td_ms = int((seconds % 1) * 1000)
    return f"{td_h:02d}:{td_m:02d}:{td_s:02d},{td_ms:03d}"


def preprocess_segment(segment: Dict[str, Any], temp_dir: Path, config: Dict[str, Any]) -> Path | None:
    """
    Process an asset into a standardized 1920x1080 30fps MP4 segment.
    Supports Ken Burns cycling for multiple images.
    """
    idx = segment["segment_index"]
    duration = segment["estimated_duration_s"]
    drawtext_filter = segment.get("drawtext_string", "")
    
    # 1. Image Cycling Logic
    raw_paths = segment.get("image_paths")
    if raw_paths:
        try:
            image_paths = json.loads(raw_paths)
        except:
            image_paths = [segment["selected_asset"]]
    else:
        image_paths = [segment["selected_asset"]]
        
    interval = config.get("image_cycling_interval_s", 12)
    enabled = config.get("image_cycling_enabled", True)
    
    if not enabled:
        n_intervals = 1
        interval = duration
    else:
        n_intervals = max(1, math.ceil(duration / interval))
    
    print(f"  [ASSEMBLER seg {idx}] {n_intervals} intervals, {len(image_paths)} unique images")
    
    interval_clips = []
    for i in range(n_intervals):
        clip_duration = min(float(interval), float(duration) - i*interval)
        if clip_duration <= 0: break
        
        img_path = Path(image_paths[i % len(image_paths)])
        out_clip = temp_dir / f"seg_{idx}_part_{i}.mp4"
        
        # Ken Burns Params
        zoom_direction = "in" if i % 2 == 0 else "out"
        pan_x = ["-0.02", "0.02", "0", "-0.02"][i % 4]
        pan_y = ["0", "-0.02", "0.02", "0"][i % 4]
        
        # FFmpeg zoompan string
        # Zoom speed 0.0015 @ 30fps = ~1.5x zoom in 10s
        frames = int(clip_duration * 30)
        if zoom_direction == "in":
            lb = "min(zoom+0.0015,1.5)"
        else:
            lb = "if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))"
            
        filt = (
            f"scale=8000:-1,zoompan=z='{lb}':d={frames}:"
            f"x='iw/2-(iw/zoom/2)+({pan_x}*iw)':y='ih/2-(ih/zoom/2)+({pan_y}*ih)':s=1920x1080"
        )
        
        if drawtext_filter and i == 0: # Only draw text on first interval for now
            filt += f",{drawtext_filter}"
            
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
            "-vf", filt, "-t", str(clip_duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-an", str(out_clip)
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        interval_clips.append(out_clip)

    # Concatenate intervals
    final_seg = temp_dir / f"seg_{idx}.mp4"
    if len(interval_clips) == 1:
        shutil.move(str(interval_clips[0]), str(final_seg))
    else:
        concat_txt = temp_dir / f"seg_{idx}_concat.txt"
        with open(concat_txt, "w") as f:
            for c in interval_clips:
                f.write(f"file '{c.resolve()}'\n")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c", "copy", str(final_seg)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    return final_seg


import shutil

def assemble_video(segments: List[Dict[str, Any]], audio_path: Path, output_path: Path, temp_dir: Path, config: Dict[str, Any]):
    """
    Concatenate preprocessed segments and mux with audio. Supports subtitles.
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
    
    # Subtitles
    srt_path = None
    if config.get("subtitles_enabled"):
        srt_path = output_path.with_suffix(".srt")
        generate_srt(audio_path, srt_path)
    
    # Mux with audio + subtitles
    cmd = ["ffmpeg", "-y", "-i", str(visuals_only), "-i", str(audio_path)]
    
    vf = []
    sub_mode = config.get("subtitle_mode", "srt")
    if srt_path and srt_path.exists() and sub_mode in ["burn", "both"]:
        # Subtitles filter needs escaped path for Windows
        esc_path = str(srt_path).replace("\\", "/").replace(":", "\\:")
        vf.append(f"subtitles='{esc_path}'")
        
    if vf:
        cmd.extend(["-vf", ",".join(vf)])
        
    cmd.extend(["-c:v", "libx264", "-c:a", "aac", "-shortest", str(output_path)])
    
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if srt_path and sub_mode not in ["srt", "both"]:
        srt_path.unlink()

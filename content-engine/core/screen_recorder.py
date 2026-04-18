import subprocess
import time
from pathlib import Path
from datetime import datetime

class ScreenRecorder:
    """FFmpeg-based screen capture (platform-agnostic)."""
    
    def __init__(self, output_dir: Path, width: int = 800, height: int = 600, fps: int = 30, method: str = "gdigrab"):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self.fps = fps
        self.method = method
        self.process = None
        self.output_file = None
    
    def start_recording(self, label: str) -> Path:
        """Start recording. Label becomes part of filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = self.output_dir / f"clip_{label}_{timestamp}.mp4"
        
        # FFmpeg command for screen recording
        cmd = [
            "ffmpeg",
            "-f", self.method,
            "-framerate", str(self.fps),
            "-i", "desktop",  # Capture entire desktop
            "-vf", f"scale={self.width}:{self.height}",  # Resize to target resolution
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-y",  # Overwrite
            str(self.output_file)
        ]
        
        self.process = subprocess.Popen(
            cmd, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        return self.output_file
    
    def stop_recording(self) -> Path:
        """Stop recording and return output file path."""
        if self.process:
            # Terminate gracefully to allow ffmpeg to finish the MP4 encapsulation
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            
        return self.output_file

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.process is not None and self.process.poll() is None

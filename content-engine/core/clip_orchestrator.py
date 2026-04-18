import time
import json
from pathlib import Path
from core.screen_recorder import ScreenRecorder
from core.game_automation import PyPongAIController

class PyPongAIClipOrchestrator:
    """Orchestrate game automation + clip recording."""

    def __init__(self, config: dict):
        self.config = config
        self.game_path = Path(config.get("game_path", "."))
        self.output_dir = Path(config.get("output_dir", "assets/clips"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.match_duration = config.get("match_duration_target", 30)
        self.startup_wait = config.get("startup_wait", 3)
        self.ui_coords = config.get("ui_coordinates", {})
        
        ffmpeg_opts = config.get("ffmpeg", {})
        self.recorder = ScreenRecorder(
            output_dir=self.output_dir,
            width=ffmpeg_opts.get("width", 800),
            height=ffmpeg_opts.get("height", 600),
            fps=ffmpeg_opts.get("fps", 30),
            method=ffmpeg_opts.get("method", "gdigrab")
        )
        self.controller = PyPongAIController(ui_coordinates=self.ui_coords)

    def record_match(self, model_name: str, duration_s: int = None) -> dict:
        """Record an automated match for a given model or setup."""
        dur = duration_s if duration_s is not None else self.match_duration
        print(f"Recording match for: {model_name}")

        # 1. Launch Game
        if not self.controller.launch_game(self.game_path, self.startup_wait):
            return {"error": "Failed to launch game"}

        # 2. Navigate (assuming Play vs AI flow)
        self.controller.click_menu_button("play_button")
        
        # Note: Model selection via UI would go here if needed.
        
        # 3. Start Recording
        mp4_path = self.recorder.start_recording(model_name)
        
        # 4. Start Match
        self.controller.click_menu_button("start_button")
        
        # 5. Wait for duration
        self.controller.wait_for_match_completion(dur)
        
        # 6. Stop Recording
        self.recorder.stop_recording()
        
        # 7. Cleanup
        self.controller.close_game()
        
        # 8. Save Metadata Sidecar
        meta_path = mp4_path.with_suffix(".json")
        metadata = {
            "model_name": model_name,
            "duration": dur,
            "path": str(mp4_path),
            "timestamp": time.time(),
            "source": "pypongai_recorder"
        }
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def record_generation_samples(self, gen_start: int, gen_end: int, sample_every_n: int) -> list:
        """Record game clips at specified generation intervals."""
        clips = []
        for gen in range(gen_start, gen_end + 1, sample_every_n):
            print(f"Recording generation {gen}...")
            # For Phase 1, we just fake the model name, actual model selection 
            # might require specific UI clicks or CLI arguments to PyPongAI.
            meta = self.record_match(f"gen_{gen}")
            clips.append(meta)
            time.sleep(2)
        return clips

    def record_gen_0_vs_gen_50(self) -> dict:
        """Record both Gen 0 and Gen 50 for comparison."""
        clips = {}
        clips["gen_0"] = self.record_match("gen_0_random", duration_s=15)
        time.sleep(2)
        clips["gen_50"] = self.record_match("gen_50_champion", duration_s=15)
        return clips

def get_pypongai_clips(output_dir: Path) -> list:
    """Helper for asset_sourcer to find recorded PyPongAI clips metadata."""
    if not output_dir.exists():
        return []
        
    results = []
    # Find all .json files in clip dir that have the "pypongai_recorder" source
    for meta_file in output_dir.glob("*.json"):
        try:
            with open(meta_file, "r") as f:
                data = json.load(f)
                if data.get("source") == "pypongai_recorder":
                    results.append({"path": data.get("path"), "metadata": data})
        except Exception:
            pass
            
    return results

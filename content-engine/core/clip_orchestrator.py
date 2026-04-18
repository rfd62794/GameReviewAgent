import time
import json
import threading
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from core.screen_recorder import ScreenRecorder
from core.game_automation import PyPongAIController

logger = logging.getLogger(__name__)

class PyPongAIClipOrchestrator:
    """Orchestrate game automation + clip recording."""

    def __init__(self, config: dict):
        self.config = config
        # Ensure game_path is absolute to avoid issues with subprocess cwd
        self.game_path = Path(config.get("game_path", ".")).resolve()
        self.output_dir = Path(config.get("output_dir", "assets/clips")).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.match_duration_seconds = config.get("match_duration_target", 30)
        self.startup_wait = config.get("startup_wait", 5) # Default increased to 5s
        self.ui_coords = config.get("ui_coordinates", {})
        
        ffmpeg_opts = config.get("ffmpeg", {})
        self.recorder = ScreenRecorder(
            output_dir=self.output_dir,
            width=ffmpeg_opts.get("width", 800),
            height=ffmpeg_opts.get("height", 600),
            fps=ffmpeg_opts.get("fps", 30),
            method=ffmpeg_opts.get("method", "gdigrab")
        )
        # Use the same resolved game_path for the controller
        self.controller = PyPongAIController(ui_coordinates=self.ui_coords)

    def record_match(self, label: str, model_name: str = "unknown") -> Optional[Dict[str, Any]]:
        """Record a single match using keyboard controls."""
        logger.info(f"Starting match recording: {label}")
        
        try:
            # 1. Launch game
            if not self.controller.launch_game(self.game_path, self.startup_wait):
                logger.error("Failed to launch game")
                return None
            
            time.sleep(1.0)
            
            # 2. Navigate to Play mode via keyboard (P key) with retries
            for attempt in range(3):
                if self.controller.press_key("p"):
                    break
                logger.warning(f"Failed to press P (Attempt {attempt+1}/3), retrying...")
                time.sleep(1.0)
            else:
                logger.error("Failed to navigate to Play mode after retries")
                self.controller.close_game()
                return None
            
            time.sleep(1.5)
            
            # 3. Start recording
            clip_path = self.recorder.start_recording(label)
            
            # 4. Start match via keyboard (S key)
            if not self.controller.press_key("s"):
                logger.error("Failed to press S key")
                self.recorder.stop_recording()
                self.controller.close_game()
                return None
            
            # 5. Wait for match duration (Phase 1 fallback)
            time.sleep(self.match_duration_seconds)
            
            # 6. Return to menu via keyboard (ESC key)
            self.controller.press_key("escape")
            time.sleep(0.5)
            
            # 7. Stop recording
            final_path = self.recorder.stop_recording()
            
            # 8. Close game
            self.controller.close_game()
            
            # 9. Generate and save metadata
            metadata = self._generate_metadata(
                label=label,
                model_name=model_name,
                clip_path=final_path,
                duration_seconds=self.match_duration_seconds,
            )
            self._save_metadata(final_path, metadata)
            
            logger.info(f"Match recording completed: {final_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error during match recording: {e}")
            self.controller.close_game()
            return None

    def record_match_with_ipc(self, label: str, model_name: str = "unknown") -> Optional[Dict[str, Any]]:
        """Record match using IPC event to detect exact completion."""
        logger.info(f"Starting match recording with IPC: {label}")
        
        try:
            # 1. Launch game via controller (handles env, stdin pipe, and stdout)
            if not self.controller.launch_game(self.game_path, self.startup_wait):
                logger.error("Failed to launch game via controller")
                return None
            
            proc = self.controller.process
            
            # Setup IPC event listener
            match_event = None
            event_received = threading.Event()
            
            def listen_for_events():
                """Read stdout and parse IPC events."""
                nonlocal match_event
                try:
                    for line in proc.stdout:
                        line = line.strip()
                        if not line: continue
                        
                        logger.debug(f"Game Output: {line}")
                        
                        # Only process lines that look like JSON events
                        if line.startswith('{"event"'):
                            try:
                                data = json.loads(line)
                                event = data.get("event")
                                
                                if event and event.get("type") == "match_complete":
                                    logger.info(f"✓ IPC Event: Match complete - {event['data']['winner']} won")
                                    match_event = event
                                    event_received.set()
                                    break
                            except json.JSONDecodeError:
                                pass
                except Exception as e:
                    logger.error(f"Error listening for IPC events: {e}")
            
            # Start listener thread
            listener_thread = threading.Thread(target=listen_for_events, daemon=True)
            listener_thread.start()
            
            # 2. Navigate and start recording
            # Controller launch_game already waits for self.startup_wait
            
            # Press P with retries
            for attempt in range(3):
                if self.controller.press_key("p"):
                    break
                logger.warning(f"Failed to press P (Attempt {attempt+1}/3), retrying...")
                time.sleep(1.0)
            
            time.sleep(1.0)
            
            clip_path = self.recorder.start_recording(label)
            
            self.controller.press_key("s")  # Start match
            time.sleep(0.5)
            
            # 3. Wait for IPC event (with timeout fallback)
            if event_received.wait(timeout=self.match_duration_seconds + 15):
                logger.info("Match completed via IPC event")
            else:
                logger.warning("IPC event timeout, match may still be running")
            
            # 4. Stop recording
            final_path = self.recorder.stop_recording()
            
            # 5. Return to menu and close
            self.controller.press_key("escape")
            time.sleep(0.5)
            self.controller.close_game()
            
            # 6. Generate metadata with IPC data
            if match_event:
                metadata = self._generate_metadata(
                    label=label,
                    model_name=model_name,
                    clip_path=final_path,
                    duration_seconds=match_event["data"]["duration_seconds"],
                    match_result=match_event["data"],
                )
            else:
                metadata = self._generate_metadata(label, model_name, final_path, self.match_duration_seconds)
            
            self._save_metadata(final_path, metadata)
            
            logger.info(f"Match recording completed: {final_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error during match recording with IPC: {e}")
            self.controller.close_game()
            return None

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
        clips["gen_0"] = self.record_match("gen_0_random_sample", model_name="gen_0")
        time.sleep(2)
        clips["gen_50"] = self.record_match("gen_50_champion_sample", model_name="gen_50")
        return clips

    def _generate_metadata(self, label: str, model_name: str, clip_path: Path, duration_seconds: float, match_result: dict = None) -> dict:
        """Standardize metadata generation for clips."""
        return {
            "label": label,
            "model_name": model_name,
            "duration": duration_seconds,
            "path": str(clip_path),
            "timestamp": time.time(),
            "source": "pypongai_recorder",
            "match_result": match_result or {}
        }

    def _save_metadata(self, clip_path: Path, metadata: dict):
        """Save metadata sidecar file."""
        meta_path = clip_path.with_suffix(".json")
        try:
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f"Metadata saved: {meta_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata to {meta_path}: {e}")

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

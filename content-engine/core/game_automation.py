import subprocess
import time
from pathlib import Path

# Note: We import pyautogui inline or handle import errors so that 
# it doesn't crash the entire ContentEngine if missing on a machine that doesn't capture videos.
try:
    import pyautogui
    import pygetwindow as gw
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)

class PyPongAIController:
    """Automate PyPongAI via keyboard/mouse."""
    
    def __init__(self, ui_coordinates: dict = None):
        self.process = None
        # Default coordinates for 800x600, overridden by config
        self.ui_coordinates = ui_coordinates or {
            "menu_title": [400, 100],
            "play_button": [200, 300],
            "train_button": [600, 300],
            "start_button": [400, 500],
            "back_button": [50, 50]
        }
        
    def launch_game(self, game_path: Path, wait_seconds: int = 3) -> bool:
        """Launch the game script and wait for it to open."""
        if not game_path.exists():
            print(f"Game path missing: {game_path}")
            return False
            
        script_path = str(game_path / "main.py")
        
        try:
            self.process = subprocess.Popen(
                ["python", script_path],
                cwd=str(game_path)
            )
            time.sleep(wait_seconds)
            self.focus_game()
            return True
        except Exception as e:
            print(f"Failed to launch game: {e}")
            return False

    def focus_game(self) -> bool:
        """Attempt to find and focus the PyPongAI window."""
        if not PYAUTOGUI_AVAILABLE:
            return False
            
        try:
            # Match strictly against the configured window title if possible
            # PyPongAI: Evolutionary Pong AI
            target_title = "PyPongAI: Evolutionary Pong AI"
            all_windows = gw.getAllWindows()
            matches = [w for w in all_windows if target_title in w.title or "PyPongAI" in w.title]
            
            if matches:
                # Sort by title length to prefer exact matches? Or just take the first.
                game_win = matches[0]
                logger.info(f"Found window: '{game_win.title}'. Activating...")
                
                game_win.activate()
                time.sleep(1.0) # Wait for OS to actually switch focus
                
                # Double focus: click in the middle
                center_x = game_win.left + game_win.width // 2
                center_y = game_win.top + game_win.height // 2
                pyautogui.click(center_x, center_y)
                time.sleep(1.0) # Wait for click to register focus
                
                logger.info(f"Focused PyPongAI window at ({center_x}, {center_y}).")
                return True
            else:
                logger.warning(f"PyPongAI window not found (Target: '{target_title}').")
                # Log all titles for debugging
                titles = [w.title for w in all_windows if w.title.strip()]
                logger.debug(f"Available window titles: {titles[:10]}...")
                return False
        except Exception as e:
            logger.error(f"Error focusing game window: {e}")
            return False

    def click_menu_button(self, button_name: str) -> bool:
        """Click a named button using predefined coordinates."""
        if not PYAUTOGUI_AVAILABLE:
            print("pyautogui not installed. Cannot automate UI.")
            return False
            
        coords = self.ui_coordinates.get(button_name)
        if not coords:
            print(f"Coordinates for '{button_name}' not found.")
            return False
            
        x, y = coords
        pyautogui.click(x, y)
        time.sleep(1) # Brief pause after clicking
        return True

    def press_key(self, key: str) -> bool:
        """
        Press a keyboard key.
        
        Args:
            key: Key name (e.g., 'p', 'escape', 's')
            
        Returns:
            True if successful
        """
        if not PYAUTOGUI_AVAILABLE:
            logger.warning("PyAutogUI not available. Cannot press key.")
            return False
        
        try:
            # Using keyDown/keyUp with a small duration is more reliable for games
            pyautogui.keyDown(key)
            time.sleep(0.1)
            pyautogui.keyUp(key)
            logger.debug(f"Pressed key (robustly): {key}")
            time.sleep(0.5)  # Increased delay for Pygame state transition
            return True
        except Exception as e:
            logger.error(f"Failed to press key {key}: {e}")
            return False
        
    def wait_for_match_completion(self, timeout_s: int) -> bool:
        """Wait blindly for the match duration (Phase 1-2 fallback)."""
        time.sleep(timeout_s)
        return True
        
    def close_game(self) -> bool:
        """Close the game process or use Alt+F4 fallback."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            return True
            
        # Alt+F4 fallback
        if PYAUTOGUI_AVAILABLE:
            pyautogui.hotkey('alt', 'f4')
            time.sleep(1)
            return True
            
        return False

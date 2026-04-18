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
            # Look for the window by title
            windows = gw.getWindowsWithTitle("PyPongAI")
            if windows:
                game_win = windows[0]
                game_win.activate()
                # Optionally click in the middle to ensure focus
                pyautogui.click(game_win.left + game_win.width // 2, 
                                game_win.top + game_win.height // 2)
                logger.info("Focused PyPongAI window.")
                return True
            else:
                logger.warning("PyPongAI window not found to focus.")
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
            pyautogui.press(key)
            logger.debug(f"Pressed key: {key}")
            time.sleep(0.3)  # Brief delay for UI to respond
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

try:
    import pyautogui
    # Note: pygetwindow is kept as a fallback, but we'll prioritize win32gui
    import pygetwindow as gw
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Low-level Windows API for focus management
try:
    import win32gui
    import win32con
    import win32process
    import ctypes
    WIN32_AVAILABLE = True
    
    # Force DPI Awareness for this process to ensure coordinates match physical pixels
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1) # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
except ImportError:
    WIN32_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)

class PyPongAIController:
    """Automate PyPongAI via keyboard/mouse."""
    
    def __init__(self, ui_coordinates: dict = None):
        self.process = None
        self.window_handle = None
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
        """Attempt to find and focus the PyPongAI window using Windows API."""
        if not WIN32_AVAILABLE:
            logger.warning("pywin32 not available. Falling back to basic focus.")
            return self._focus_game_fallback()
            
        try:
            target_title = "PyPongAI: Evolutionary Pong AI"
            hwnd = win32gui.FindWindow(None, target_title)
            
            # Fallback to partial match if exact title isn't found
            if not hwnd:
                def enum_handler(h, l):
                    if "PyPongAI" in win32gui.GetWindowText(h):
                        l.append(h)
                hwnds = []
                win32gui.EnumWindows(enum_handler, hwnds)
                if hwnds:
                    hwnd = hwnds[0]
            
            if hwnd:
                self.window_handle = hwnd
                logger.debug(f"Targeting window hwnd: {hwnd}")
                
                # Ensure window is shown
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                time.sleep(0.1)
                
                # Force to foreground
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5) # Wait for OS switch
                
                # Double focus with a physical click
                rect = win32gui.GetWindowRect(hwnd)
                center_x = rect[0] + (rect[2] - rect[0]) // 2
                center_y = rect[1] + (rect[3] - rect[1]) // 2
                
                if PYAUTOGUI_AVAILABLE:
                    pyautogui.click(center_x, center_y)
                    time.sleep(0.5)
                
                logger.info(f"Focused PyPongAI window at ({center_x}, {center_y})")
                return True
            else:
                logger.warning(f"PyPongAI window not found (Target: '{target_title}').")
                return False
        except Exception as e:
            logger.error(f"Error focusing game window with win32api: {e}")
            return False

    def _focus_game_fallback(self) -> bool:
        """Legacy pygetwindow fallback focus logic."""
        if not PYAUTOGUI_AVAILABLE: return False
        try:
            windows = gw.getWindowsWithTitle("PyPongAI")
            if windows:
                game_win = windows[0]
                game_win.activate()
                pyautogui.click(game_win.left + game_win.width // 2, 
                                game_win.top + game_win.height // 2)
                return True
        except Exception:
            return False
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
        Press a keyboard key with focus verification.
        """
        if not PYAUTOGUI_AVAILABLE:
            logger.warning("PyAutogUI not available. Cannot press key.")
            return False
        
        # Verify focus before pressing
        if WIN32_AVAILABLE and self.window_handle:
            if win32gui.GetForegroundWindow() != self.window_handle:
                logger.debug("Lost focus, re-focusing...")
                self.focus_game()

        try:
            # Using keyDown/keyUp with a small duration is more reliable for games
            pyautogui.keyDown(key)
            time.sleep(0.1)
            pyautogui.keyUp(key)
            logger.debug(f"Pressed key (robustly): {key}")
            time.sleep(0.8)  # Generous delay for Pygame state transition
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

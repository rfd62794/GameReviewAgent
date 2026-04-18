import subprocess
import time
from pathlib import Path
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
    import win32api
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
        """Attempt to find and focus the PyPongAI window using PID targeting and Thread Attachment."""
        if not WIN32_AVAILABLE:
            logger.warning("pywin32 not available. Falling back to basic focus.")
            return self._focus_game_fallback()
            
        try:
            target_pid = self.process.pid if self.process else None
            hwnd = None
            
            # 1. Targeted search by PID (Preferred to avoid orphaned windows)
            if target_pid:
                def find_by_pid(h, result):
                    _, pid = win32process.GetWindowThreadProcessId(h)
                    if pid == target_pid and win32gui.IsWindowVisible(h):
                        result.append(h)
                hwnds = []
                win32gui.EnumWindows(find_by_pid, hwnds)
                if hwnds:
                    hwnd = hwnds[0]
            
            # 2. Fallback to title search if PID matching failed
            if not hwnd:
                target_title = "PyPongAI: Evolutionary Pong AI"
                hwnd = win32gui.FindWindow(None, target_title)
            
            if hwnd:
                self.window_handle = hwnd
                logger.debug(f"Targeting window hwnd: {hwnd} (PID: {target_pid})")
                
                # 3. Use AttachThreadInput to bypass 'Access Denied' on SetFocus
                # This binds our script's input thread to the game's input thread
                self._attach_input(True)
                
                # 4. Minimize and Restore (The "Focus Kick")
                # This forces Windows to re-evaluate the window's foreground priority
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                time.sleep(0.1)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                
                # 5. Bring to foreground
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5) 
                
                # 6. Double focus with a physical click
                rect = win32gui.GetWindowRect(hwnd)
                center_x = rect[0] + (rect[2] - rect[0]) // 2
                center_y = rect[1] + (rect[3] - rect[1]) // 2
                
                if PYAUTOGUI_AVAILABLE:
                    pyautogui.click(center_x, center_y)
                    time.sleep(0.5)
                
                logger.info(f"Focused PyPongAI window (PID: {target_pid}) at ({center_x}, {center_y})")
                return True
            else:
                logger.warning("PyPongAI window not found.")
                return False
        except Exception as e:
            logger.error(f"Error focusing game window: {e}")
            return False

    def _attach_input(self, attach: bool):
        """Bind automation thread input to target window's thread input."""
        if not WIN32_AVAILABLE or not self.window_handle:
            return
            
        try:
            target_thread, _ = win32process.GetWindowThreadProcessId(self.window_handle)
            current_thread = win32api.GetCurrentThreadId()
            
            if target_thread != current_thread:
                # Use ctypes for more reliable access to user32
                ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, attach)
        except Exception as e:
            logger.debug(f"AttachThreadInput failed: {e}")

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
        Press a keyboard key using low-level Hardware ScanCodes (DirectInput style).
        """
        if not WIN32_AVAILABLE:
            # Fallback to pyautogui if win32 is missing
            return self._press_key_pyautogui(key)
        
        # Verify focus before pressing
        if self.window_handle:
            if win32gui.GetForegroundWindow() != self.window_handle:
                logger.debug("Lost focus, re-focusing...")
                self.focus_game()

        try:
            # Hardware ScanCodes for common keys
            # P = 0x19, S = 0x1F, ESC = 0x01
            scancodes = {
                "p": 0x19,
                "s": 0x1F,
                "escape": 0x01,
                "q": 0x10,
                "t": 0x14,
                "l": 0x26,
                "m": 0x32,
                "a": 0x1E,
                "c": 0x2E
            }
            
            code = scancodes.get(key.lower())
            if not code:
                logger.warning(f"No ScanCode found for '{key}', falling back to pyautogui.")
                return self._press_key_pyautogui(key)

            logger.debug(f"Pressing key via SendInput (ScanCode: {hex(code)})")
            
            # Key Down
            self._send_input_key(code, down=True)
            time.sleep(0.1)
            # Key Up
            self._send_input_key(code, down=False)
            
            time.sleep(1.0) # Generous delay for state transition
            return True
        except Exception as e:
            logger.error(f"Failed to press key {key} via SendInput: {e}")
            return self._press_key_pyautogui(key)

    def _send_input_key(self, scancode: int, down: bool):
        """Low-level SendInput implementation for hardware scancodes (64-bit compatible)."""
        # Constants
        KEYEVENTF_SCANCODE = 0x0008
        KEYEVENTF_KEYUP = 0x0002
        
        # Structure definitions for 64-bit alignment
        class KBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", ctypes.c_ushort),
                        ("wScan", ctypes.c_ushort),
                        ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong),
                        ("dwExtraInfo", ctypes.c_void_p)]

        class INPUT_UNION(ctypes.Union):
            _fields_ = [("ki", KBDINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong),
                        ("padding", ctypes.c_ulong), # 4-byte padding for 8-byte alignment of union on 64-bit
                        ("iu", INPUT_UNION)]

        flags = KEYEVENTF_SCANCODE
        if not down:
            flags |= KEYEVENTF_KEYUP
            
        kb = KBDINPUT(0, scancode, flags, 0, None)
        iu = INPUT_UNION(ki=kb)
        # Note: on 64-bit, the 'padding' is between 'type' and 'iu'
        inp = INPUT(1, 0, iu) # 1 = INPUT_KEYBOARD
        
        res = ctypes.windll.user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))
        if res == 0:
            logger.error(f"SendInput failed with result: {res} (GetLastError: {ctypes.windll.kernel32.GetLastError()})")

    def _press_key_pyautogui(self, key: str) -> bool:
        """Fallback keyboard press logic."""
        if not PYAUTOGUI_AVAILABLE: return False
        try:
            pyautogui.keyDown(key)
            time.sleep(0.1)
            pyautogui.keyUp(key)
            return True
        except Exception:
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

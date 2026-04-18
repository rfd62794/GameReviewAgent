"""
Diagnostic script to verify window state and input focus.
Helps identify why keyboard input isn't reaching PyPongAI.
"""

import subprocess
import time
import sys
from pathlib import Path

# Try to import pyautogui, but don't fail if missing
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("WARNING: PyAutogUI not installed. Install with: pip install pyautogui")

# Try Windows-specific imports
try:
    import win32gui
    import win32process
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("WARNING: pywin32 not installed. Install with: pip install pywin32")


def find_game_window():
    """Find PyPongAI window by title."""
    if not WIN32_AVAILABLE:
        print("❌ pywin32 not available. Cannot find window.")
        return None
    
    hwnd = win32gui.FindWindow(None, "PyPongAI")
    if hwnd:
        print(f"✓ Found window (hwnd={hwnd})")
        return hwnd
    
    # Try alternative title
    hwnd = win32gui.FindWindow(None, "PyPongAI: Evolutionary Pong AI")
    if hwnd:
        print(f"✓ Found window with full title (hwnd={hwnd})")
        return hwnd
    
    print("❌ Window not found. Available windows:")
    
    def enum_windows(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if "pong" in title.lower() or "python" in title.lower():
            print(f"  - {title} (hwnd={hwnd})")
        return True
    
    win32gui.EnumWindows(enum_windows, None)
    return None


def get_window_info(hwnd):
    """Get window position, size, and focus state."""
    if not WIN32_AVAILABLE:
        return None
    
    try:
        rect = win32gui.GetWindowRect(hwnd)
        x1, y1, x2, y2 = rect
        width = x2 - x1
        height = y2 - y1
        
        is_visible = win32gui.IsWindowVisible(hwnd)
        is_foreground = win32gui.GetForegroundWindow() == hwnd
        
        print(f"  Position: ({x1}, {y1}) to ({x2}, {y2})")
        print(f"  Size: {width}x{height}")
        print(f"  Visible: {is_visible}")
        print(f"  Foreground: {is_foreground}")
        
        return {
            "rect": rect,
            "width": width,
            "height": height,
            "visible": is_visible,
            "foreground": is_foreground,
        }
    except Exception as e:
        print(f"  Error getting window info: {e}")
        return None


def focus_window(hwnd):
    """Bring window to foreground and give it focus."""
    if not WIN32_AVAILABLE:
        return False
    
    try:
        # Unhide if minimized
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        time.sleep(0.2)
        
        # Bring to foreground
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        
        # Set focus
        win32gui.SetFocus(hwnd)
        time.sleep(0.2)
        
        print("✓ Window focused and brought to foreground")
        return True
    except Exception as e:
        print(f"❌ Failed to focus window: {e}")
        return False


def test_keyboard_input():
    """Test if keyboard input works when focused."""
    if not PYAUTOGUI_AVAILABLE:
        print("⚠ PyAutogUI not available. Skipping keyboard test.")
        return False
    
    print("\nTesting keyboard input...")
    print("  (Watch for any response from the game window)")
    
    # Try pressing 'P' and watch for response
    print("  Pressing 'P' key...")
    pyautogui.press('p')
    time.sleep(0.5)
    
    print("  ✓ Key press sent")
    return True


def check_dpi_scaling():
    """Check if Windows DPI scaling is set to 100%."""
    try:
        import ctypes
        
        # Get DPI scaling factor
        dpi = ctypes.windll.user32.GetDpiForSystem()
        scaling = (dpi / 96) * 100  # 96 DPI = 100%
        
        print(f"  DPI: {dpi} ({scaling:.0f}% scaling)")
        
        if scaling != 100:
            print(f"  ⚠ DPI scaling is at {scaling:.0f}%")
            print(f"    PyAutogUI coordinates may be offset by {scaling/100:.2f}x")
            print(f"    Check: Settings → Display → Scale and layout")
            return False
        
        return True
    except Exception as e:
        print(f"  Could not check DPI: {e}")
        return None


def main():
    """Run diagnostics."""
    print("=" * 60)
    print("PyPongAI Input Focus Diagnostics")
    print("=" * 60)
    
    print("\n1. Checking DPI Scaling")
    print("-" * 40)
    check_dpi_scaling()
    
    print("\n2. Launching PyPongAI")
    print("-" * 40)
    # Correct path for sibling repo
    game_path = Path(__file__).parent.parent / "PyPongAI"
    if not game_path.exists():
        # Try one more level up
        game_path = Path(__file__).parent.parent.parent / "PyPongAI"
        
    if not game_path.exists():
        print(f"❌ PyPongAI not found. Search path: {game_path}")
        return 1
    
    print(f"  Launching from: {game_path}")
    proc = subprocess.Popen(
        ["python", "main.py"],
        cwd=game_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"  Process ID: {proc.pid}")
    
    print("\n3. Waiting for window...")
    print("-" * 40)
    time.sleep(3)  # Wait for game to fully launch
    
    hwnd = find_game_window()
    if not hwnd:
        print("❌ Could not find game window. Game may not have launched.")
        proc.terminate()
        return 1
    
    print("\n4. Window Information")
    print("-" * 40)
    get_window_info(hwnd)
    
    print("\n5. Focusing Window")
    print("-" * 40)
    if focus_window(hwnd):
        time.sleep(0.5)
        
        print("\n6. Re-checking Focus State")
        print("-" * 40)
        get_window_info(hwnd)
        
        print("\n7. Testing Keyboard Input")
        print("-" * 40)
        test_keyboard_input()
    
    print("\n8. Cleanup")
    print("-" * 40)
    print("  Closing game...")
    time.sleep(2)
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("  ✓ Game closed")
    
    print("\n" + "=" * 60)
    print("Diagnostics Complete")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

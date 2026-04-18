"""
Game Automation via stdin IPC Bridge

Sends JSON commands to PyPongAI via stdin instead of synthetic keyboard input.
More reliable, works with minimized windows, no focus required.
"""

import json
import subprocess
import logging
import time
import os
from pathlib import Path
from typing import Optional

# Keep these for basic window status discovery if needed
try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

logger = logging.getLogger(__name__)


class PyPongAIController:
    """Control PyPongAI via stdin pipe (IPC)."""
    
    def __init__(self, ui_coordinates: dict = None):
        """
        Initialize controller for pipe-based IPC.
        """
        self.process: Optional[subprocess.Popen] = None
        self.stdin = None
        self.window_handle = None
    
    def launch_game(self, game_path: Path, wait_seconds: int = 5) -> bool:
        """
        Launch PyPongAI with stdin pipe for automation.
        
        Returns:
            True if launched successfully
        """
        if not game_path.exists():
            logger.error(f"Game path not found: {game_path}")
            return False
            
        script_path = str(game_path / "main.py")
        
        try:
            # Set environment variable to enable automation bridge in child
            env = os.environ.copy()
            env["PYPONGAI_AUTOMATION"] = "true"
            
            # Launch with stdin pipe + stdout capture
            self.process = subprocess.Popen(
                ["python", script_path],
                cwd=str(game_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffering
                env=env
            )
            
            self.stdin = self.process.stdin
            logger.info(f"Game launched (PID={self.process.pid}) with stdin pipe")
            
            # Wait for full initialization (Pygame window creation)
            time.sleep(wait_seconds)
            
            # Verify bridge is alive with a ping
            if not self._ping_bridge():
                logger.warning("Automation bridge not responding to ping")
                # We'll continue anyway, maybe it just took longer to start
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to launch game: {e}")
            return False

    def _ping_bridge(self) -> bool:
        """Test the pipe with a ping command."""
        return self._send_command({"command": "ping"})

    def focus_game(self) -> bool:
        """
        IPC version of focus_game. 
        Actually not strictly necessary for IPC, 
        but we'll find the window handle for status checks.
        """
        if not WIN32_AVAILABLE or not self.process:
            return False
            
        target_pid = self.process.pid
        hwnd = None
        
        def find_by_pid(h, result):
            _, pid = win32process.GetWindowThreadProcessId(h)
            title = win32gui.GetWindowText(h)
            if pid == target_pid and win32gui.IsWindowVisible(h) and "PyPongAI" in title:
                result.append(h)
                
        hwnds = []
        win32gui.EnumWindows(find_by_pid, hwnds)
        if hwnds:
            hwnd = hwnds[0]
            self.window_handle = hwnd
            return True
        return False

    def press_key(self, key: str) -> bool:
        """
        Press a key by sending a JSON command via the stdin pipe.
        """
        return self._send_command({"command": "press", "key": key.lower()})

    def _send_command(self, command: dict) -> bool:
        """Send a JSON command via stdin pipe."""
        if self.stdin is None or self.process.poll() is not None:
            logger.error("Game process not running or pipe closed")
            return False
        
        try:
            json_str = json.dumps(command)
            self.stdin.write(json_str + "\n")
            self.stdin.flush()
            logger.debug(f"IPC sent: {json_str}")
            return True
        except Exception as e:
            logger.error(f"Failed to send IPC command: {e}")
            return False

    def close_game(self) -> bool:
        """Close the game process."""
        if self.process:
            # Try graceful quit via IPC first
            self.press_key("q")
            time.sleep(0.5)
            
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None
            self.stdin = None
            return True
        return False

    def click_menu_button(self, button_name: str) -> bool:
        """Legacy compatibility - IPC currently doesn't implement coordinates."""
        logger.warning(f"click_menu_button('{button_name}') called but IPC bridge has no coordinate map.")
        return False

    def wait_for_match_completion(self, timeout_s: int) -> bool:
        """Wait for match completion."""
        time.sleep(timeout_s)
        return True

"""
Quick test of the Pipe-Driven Automation bridge.
"""

import time
import logging
from pathlib import Path
from core.game_automation import PyPongAIController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_bridge():
    # 1. Initialize controller
    controller = PyPongAIController()
    
    # 2. Path to PyPongAI (relative to content-engine)
    game_path = Path("../../PyPongAI")
    
    print(f"Launching game from {game_path.absolute()}...")
    
    # 3. Launch
    if not controller.launch_game(game_path, wait_seconds=5):
        print("FAIL: Failed to launch game.")
        return
        
    print("SUCCESS: Game launched and bridge connected.")
    
    # 4. Try basic commands
    print("Sending 'P' (Go to Play/Lobby)...")
    controller.press_key("p")
    time.sleep(2)
    
    print("Sending 'ESC' (Back to Menu)...")
    controller.press_key("escape")
    time.sleep(2)
    
    print("Sending 'Q' (Quit)...")
    controller.close_game()
    
    print("SUCCESS: Test completed.")

if __name__ == "__main__":
    test_bridge()

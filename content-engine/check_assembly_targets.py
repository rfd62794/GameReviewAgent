import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.db import get_connection

def main():
    conn = get_connection()
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    scripts = conn.execute("SELECT id, topic_id FROM scripts").fetchall()
    print("\n--- SCRIPTS ---")
    for s in scripts:
        print(f"ID: {s['id']} | Topic: {s['topic_id']}")
        
    audio_files = list(Path("assets/audio").glob("*.mp3")) if Path("assets/audio").exists() else []
    if not audio_files:
        audio_files = list(Path("output").glob("*.mp3"))
        
    print("\n--- AUDIO FILES ---")
    for a in audio_files:
        print(f"  {a.name}")
        
    conn.close()

if __name__ == "__main__":
    main()

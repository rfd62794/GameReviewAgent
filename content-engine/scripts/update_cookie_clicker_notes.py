import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import get_connection

def update_style_notes():
    conn = get_connection()
    try:
        notes = "pixel art, golden ornate UI borders, dark cosmic background, cookie iconography, heavenly/angelic aesthetic"
        conn.execute("UPDATE game_clip_index SET style_notes = ? WHERE game_title = 'Cookie Clicker'", (notes,))
        conn.commit()
        print("✓ Cookie Clicker style notes updated.")
    finally:
        conn.close()

if __name__ == "__main__":
    update_style_notes()

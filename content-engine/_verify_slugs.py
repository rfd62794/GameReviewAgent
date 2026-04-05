import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.wiki_sourcer import find_game_slug

def verify():
    print("\n--- SLUG RESOLUTION VERIFICATION ---")
    games = ["Cookie Clicker", "Adventure Capitalist"]
    for game in games:
        slug = find_game_slug(game)
        print(f"Game: {game:22} | Resolved Slug: {slug}")
    print("------------------------------------\n")

if __name__ == "__main__":
    verify()

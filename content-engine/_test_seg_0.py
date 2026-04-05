import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.llm_client import create_llm_client
from dotenv import load_dotenv

load_dotenv()

def test_seg_0():
    prompt = "Cookie Clicker ascension button press digital art, vibrant game UI screenshot style, 4K"
    model = "google/gemini-2.5-flash-image"
    
    print(f"--- LIVE TEST: Segment 0 ---")
    print(f"Prompt: {prompt}")
    print(f"Model:  {model}")
    
    client = create_llm_client(model=model)
    image_bytes = client.generate_image(
        prompt=prompt,
        aspect_ratio="16:9",
        image_size="2K"
    )
    
    if image_bytes:
        print(f"SUCCESS: Received {len(image_bytes)} bytes.")
        out_dir = Path("assets/generated")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "test_seg_0_live.png"
        with open(out_path, "wb") as f:
            f.write(image_bytes)
        print(f"SAVED:   {out_path.absolute()}")
    else:
        print("FAILED:  No image bytes received.")

if __name__ == "__main__":
    test_seg_0()

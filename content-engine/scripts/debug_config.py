import yaml
import os
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

print(f"RAW CONFIG: {_cfg.get('assembly')}")
print(f"youtube_clip_enabled IN CONFIG: {_cfg.get('assembly', {}).get('youtube_clip_enabled')}")

from core.asset_sourcer import YOUTUBE_CLIP_ENABLED
print(f"YOUTUBE_CLIP_ENABLED in asset_sourcer: {YOUTUBE_CLIP_ENABLED}")

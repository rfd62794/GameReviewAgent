import yaml
import os
from pathlib import Path

_CONFIG_PATH = Path("config.yaml")
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

print(f"RAW CONFIG: {_cfg.get('assembly')}")
print(f"youtube_clip_enabled IN CONFIG: {_cfg.get('assembly', {}).get('youtube_clip_enabled')}")

from core.asset_sourcer import YOUTUBE_CLIP_ENABLED
print(f"YOUTUBE_CLIP_ENABLED in asset_sourcer: {YOUTUBE_CLIP_ENABLED}")

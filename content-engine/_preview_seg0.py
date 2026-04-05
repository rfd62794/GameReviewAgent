import sys, os
sys.path.insert(0, ".")
os.environ["PYTHONIOENCODING"] = "utf-8"

from core.db import get_connection
from core.asset_sourcer import _build_pollinations_prompt
from core.assembler import _extract_key_phrase, _escape_drawtext

conn = get_connection()
conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
seg = conn.execute(
    "SELECT * FROM asset_briefs WHERE script_id = 1 AND segment_index = 0"
).fetchone()
conn.close()

poll_prompt = _build_pollinations_prompt(seg)
key_phrase  = _extract_key_phrase(seg["segment_text"])
escaped     = _escape_drawtext(key_phrase)
drawtext    = (
    f"drawbox=x=0:y=810:w=iw:h=140:color=black@0.55:t=fill,"
    f"drawtext=text='{escaped}'"
    f":fontsize=52:fontcolor=white:x=(w-text_w)/2:y=840"
    f":shadowcolor=black@0.6:shadowx=2:shadowy=2"
)

print()
print("=== SEGMENT 0 PREVIEW ===")
print(f"segment_text (first 120 chars):")
print(f"  {seg['segment_text'][:120]}")
print()
print("1. POLLINATIONS PROMPT:")
print(f"   {poll_prompt}")
print()
print("2. DRAWTEXT OVERLAY:")
print(f"   key_phrase : \"{key_phrase}\"")
print(f"   filter     : {drawtext}")
print()
print(f"3. ESTIMATED DURATION: {seg['estimated_duration_s']}s")
print()
print("=== END PREVIEW ===")

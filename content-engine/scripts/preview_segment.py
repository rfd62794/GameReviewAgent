import sys, os
sys.path.insert(0, ".")
os.environ["PYTHONIOENCODING"] = "utf-8"
OUT = open("_preview_seg0_out.txt", "w", encoding="utf-8")
def pr(s=""): OUT.write(s + "\n"); print(s)

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

pr()
pr("=== SEGMENT 0 PREVIEW ===")
pr(f"segment_text (first 120 chars):")
pr(f"  {seg['segment_text'][:120]}")
pr()
pr("1. POLLINATIONS PROMPT:")
pr(f"   {poll_prompt}")
pr()
pr("2. DRAWTEXT OVERLAY:")
pr(f"   key_phrase : \"{key_phrase}\"")
pr(f"   filter     : {drawtext}")
pr()
pr(f"3. ESTIMATED DURATION: {seg['estimated_duration_s']}s")
pr()
pr("=== END PREVIEW ===")
OUT.close()
print("\n[written to _preview_seg0_out.txt]")

**ContentEngine**

Software Design Document v0.4

*AI-Powered YouTube Content Pipeline*

April 2026  —  RFD IT Services Ltd.

*v0.4 adds: ADR-006 YouTube Clip Sourcing via yt-dlp \+ LLM Relevance Judgment*

# **Revision History**

| v0.1 — Apr 2026 | Initial SDD. 7-phase pipeline, dual-format output, SQLite, OpenRouter. |
| :---- | :---- |
| **v0.2 — Apr 2026** | ADR-001/002/003. Manual Brief Mode. Dual-format JSON contract. WAL. |
| **v0.3 — Apr 2026** | ADR-004/005. OpenRouter unified client. Transcript-first visual assembly. P3b/P4/P7. Pexels \+ Wikimedia \+ local \+ AI image sourcing. Edge TTS confirmed. |
| **v0.4 — Apr 2026** | ADR-006. Pexels stock clips replaced as primary source. YouTube clip sourcing via yt-dlp \+ LLM relevance judgment added as primary clip source. Director-provided links supported. Confidence threshold 0.8. Pollinations.ai fallback on threshold miss. |

# **1\. Purpose & Scope**

ContentEngine is a standalone Python pipeline for generating, researching, and packaging short-form YouTube content. It operates as an AI-assisted production system with a human director at the top of the execution model.

As of v0.4, the pipeline sources gameplay and concept clips from YouTube using yt-dlp with LLM-judged relevance scoring, replacing generic Pexels stock clips as the primary video source.

# **2\. Asset Sourcing Layer (Updated v0.4)**

## **2.1 Source Priority Order**

Priority order for clip sourcing per segment, evaluated in sequence:

| 1\. Local gameplay library | assets/gameplay/ — director-captured recordings. Checked first. Exact game title match required. |
| :---- | :---- |
| **2\. Director-provided links** | sources\[\] in manual brief JSON with source\_type='creator'. yt-dlp fetches transcript. LLM judges relevance. If confidence ≥ 0.8, clip downloaded. |
| **3\. YouTube auto-search** | yt-dlp searches YouTube for segment keywords. 5 candidates evaluated. LLM judges each. Highest confidence ≥ 0.8 wins. |
| **4\. Wikimedia Commons** | Game screenshots and official artwork. Used for named game references when no clip qualifies. |
| **5\. Pollinations.ai (fallback)** | AI image generation. Used when no clip or Wikimedia asset meets threshold. Abstract concept prompt generated from segment text. |
| **6\. Pexels stills** | Last resort for non-game concept segments only. Never used for game-specific segments. |

*NOTE: Pexels video clips are removed from the sourcing pipeline entirely. Generic gaming stock footage (hands on controller, blurry monitor) is not acceptable for game mechanics content.*

## **2.2 YouTube Clip Sourcing Flow (ADR-006)**

Full flow for each script segment requiring a clip:

| Step 1 — Query generation | P3b generates a YouTube search query from segment keywords. Query targets gameplay demonstration, not commentary. Example: 'Cookie Clicker ascension prestige gameplay' |
| :---- | :---- |
| **Step 2 — Candidate retrieval** | yt-dlp searches YouTube. Returns 5 candidate videos with title, channel, duration, view count, description. |
| **Step 3 — Transcript fetch** | yt-dlp fetches auto-generated captions for each candidate. Timeout: 15s per video. Skip on failure. |
| **Step 4 — LLM relevance judgment** | DeepSeek via OpenRouter judges each candidate. Input: segment text \+ video title \+ transcript excerpt (500 words around keyword match). Output: JSON {relevant: bool, timestamp\_start: int, timestamp\_end: int, confidence: float, reason: str} |
| **Step 5 — Threshold gate** | Highest confidence candidate evaluated. If confidence ≥ 0.8: download clip. If confidence \< 0.8: fall back to Pollinations.ai still. |
| **Step 6 — Clip download** | yt-dlp downloads only the relevant segment (timestamp\_start to timestamp\_end \+ 2s buffer). Stored in assets/clips/ with metadata JSON. |

## **2.3 LLM Judge Contract**

The relevance judge uses DeepSeek via OpenRouter. Prompt contract enforces strict JSON output. The judge is explicitly forbidden from accepting clips based on title alone — transcript content must confirm relevance.

| Model | deepseek/deepseek-chat via OpenRouter |
| :---- | :---- |
| **Input** | Segment text (full) \+ video title \+ channel \+ transcript excerpt (500 words centred on best keyword match) |
| **Output schema** | { relevant: bool, timestamp\_start: int, timestamp\_end: int, confidence: float 0.0-1.0, reason: str (max 100 chars) } |
| **Confidence 0.8 threshold** | Auto-accept. Clip downloaded. |
| **Confidence 0.5-0.79** | Logged as candidate. Not downloaded. Used only if all 5 candidates fail threshold. |
| **Confidence \< 0.5** | Rejected. Not logged as candidate. |
| **Fallback trigger** | All 5 candidates below 0.8 → Pollinations.ai still generated from segment text. |
| **Forbidden** | Accepting based on video title alone. Transcript must confirm. |

## **2.4 Director-Provided Links**

The manual brief JSON sources\[\] array accepts YouTube URLs with source\_type='creator'. These are evaluated before auto-search and given priority in the judgment queue. Director links bypass the search step but still go through LLM relevance judgment and the 0.8 confidence threshold.

| Brief field | sources\[\].url with source\_type='creator' or source\_type='gameplay' |
| :---- | :---- |
| **Processing** | yt-dlp fetches transcript. LLM judges relevance against each segment. Best match per segment selected. |
| **Multiple links** | All provided links evaluated against all segments. One clip per segment maximum. |
| **Override** | Director can force a specific link to a specific segment via sources\[\].segment\_hint field (optional integer). |

## **2.5 Config Flags (additions)**

| youtube\_clip\_enabled | Boolean. Default: true. Set false to skip YouTube sourcing entirely. |
| :---- | :---- |
| **youtube\_candidates** | Integer. Default: 5\. Number of candidates evaluated per segment. |
| **youtube\_confidence\_threshold** | Float. Default: 0.8. Minimum confidence for auto-accept. |
| **youtube\_clip\_timeout** | Integer. Default: 15\. Seconds before yt-dlp transcript fetch times out. |
| **youtube\_clip\_buffer\_s** | Integer. Default: 2\. Seconds added to each end of downloaded clip. |

# **3\. Full Pipeline Stages (Updated)**

| Phase | Name | Responsibility | Output |
| :---- | :---- | :---- | :---- |
| P1 | Brief Generation | AI (DeepSeek via OpenRouter) | Bypassed in Manual Mode |
| P2 | Research Execution | AI \+ Web Sources | Bypassed in Manual Mode |
| P3 | Script Drafting | claude-sonnet-4-6 via OpenRouter | JSON: hook\_short\_script \+ mid\_form\_body |
| P3b | Transcript Segmentation | Python | Paragraph segments \+ visual\_type \+ YouTube search queries |
| P4 | Asset Sourcing | yt-dlp \+ LLM judge \+ Wikimedia \+ Pollinations | assets/clips/ and assets/stills/ keyed to segment |
| P4b | Asset Selection | Python — confidence scoring | selected\_asset per segment written to asset\_briefs |
| P6 | Voice Synthesis | Edge TTS — zero cost | audio/hook.mp3 \+ audio/body.mp3 |
| P7 | FFmpeg Assembly | FFmpeg \+ Python | output/video.mp4 — Ken Burns stills, direct clips, optional SRT |

# **4\. ADR-006: YouTube Clip Sourcing**

| ADR-006 | YouTube Clip Sourcing via yt-dlp \+ LLM Relevance Judgment |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | Pexels stock video for game mechanics content returns generic gaming footage (hands on controller, blurry monitor) that is visually irrelevant and signals low production quality to viewers. Game-specific footage requires game-specific sourcing. |
| **Decision** | YouTube is the primary clip source for all game-specific segments. yt-dlp handles search and download. DeepSeek via OpenRouter judges transcript relevance per candidate. 5 candidates evaluated per segment. Confidence threshold 0.8 for auto-accept. Director-provided YouTube links evaluated first with priority. Clips below threshold fall back to Pollinations.ai AI-generated still. |
| **Consequences** | Clips are contextually relevant to script content rather than generically gaming-adjacent. Director can curate sources via brief JSON. LLM judgment adds one DeepSeek call per candidate per segment — cost is fractional at MVP volume. yt-dlp dependency added. Fair use commentary context applies to game mechanics analysis content. |
| **Rejected alternatives** | Pexels video: returns irrelevant generic gaming stock. Manual clip selection: defeats pipeline automation goal. Screen recording only: requires director time per video. |
| **Candidates** | 5 per segment — balanced speed vs coverage. |
| **Threshold** | 0.8 — balanced quality gate. Below threshold falls back to Pollinations.ai still, never a low-confidence clip. |

# **5\. Open Questions**

| OQ-001 — ACTIVE | Web search API for P2 (Phase 3+): Brave Search preferred. |
| :---- | :---- |
| **OQ-003** | Channel name and identity: separate from rfditservices.com or linked? |
| **OQ-004** | Content cadence target: affects queue depth planning. |
| **OQ-005** | GDC Vault free tier access. Confirm before Phase 3\. |
| **OQ-006** | AI image quality: Pollinations.ai acceptable for fallback stills? Evaluate on first abstract segment. |
| **OQ-007** | Voice identity: GuyNeural flagged as generic. Evaluate Kokoro TTS post-Phase 2\. |
| **OQ-008 — NEW** | yt-dlp YouTube search reliability: YouTube actively rate-limits automated search. May need YouTube Data API v3 (free tier: 10,000 units/day) as fallback for search step. Monitor on first full run. |

# **6\. Next Steps**

* ADR-006 directive to Antigravity: replace P4 Pexels clip sourcing with yt-dlp \+ LLM judge

* Add yt-dlp to requirements.txt

* Add YouTube search query generation to P3b segmentation output

* Implement LLM judge prompt contract in prompts/clip\_relevance.md

* Test on idle clicker prestige script — segment 0 (hook) first

* Monitor OQ-008 — YouTube rate limiting on first automated search run

* Provide YouTube links for Cookie Clicker and Adventure Capitalist gameplay to brief JSON

*ContentEngine SDD v0.4  —  RFD IT Services Ltd.  —  April 2026*
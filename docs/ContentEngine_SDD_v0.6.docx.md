**ContentEngine**

Software Design Document v0.6

*AI-Powered YouTube Content Pipeline*

April 2026  —  RFD IT Services Ltd.

*v0.6 adds: ADR-008 Reference Image Grounding • ADR-009 Image Cycling • wiki\_sourcer.py • reference\_manager.py • Subtitle SRT system*

# **1\. Revision History**

| v0.1–0.4 | Iterative pipeline development. Manual Brief Mode, dual-format script, WAL, OpenRouter client, YouTube clip sourcing, game clip index. |
| :---- | :---- |
| **v0.5 — Apr 2026** | Definitive architecture. 9-stage pipeline plan. Section 11 Module Contracts. SoC/SRP violation inventory. Naming convention locked. |
| **v0.6 — Apr 2026** | First complete video produced. OpenRouter image generation integrated (Gemini flash). ADR-008: Reference Image Grounding via Fandom API → clip frame → Google Images → Director flag. ADR-009: Image Cycling via Ken Burns variation (default) or variant generation (optional toggle). Subtitle SRT system added. wiki\_sourcer.py and reference\_manager.py added as proper modules. |

# **2\. Purpose & Scope**

ContentEngine is a standalone Python pipeline for generating, researching, and packaging short-form YouTube content. It operates as an AI-assisted production system with a human director at the top of the execution model.

As of v0.6, the pipeline produces complete MP4 videos with AI-generated images grounded to real game reference screenshots, cycling visuals to avoid static holds, and Whisper-generated subtitle SRT files synced to actual audio output.

The first complete video was produced in the v0.5 build session and validated as publishable quality with minor improvements identified.

# **3\. Pipeline Summary**

| Code | Name | Status | Core Module(s) | Input | Output |
| :---- | :---- | :---- | :---- | :---- | :---- |
| P1 | Brief Generation | FUTURE | (TBD) | Director topic | Research brief |
| P2 | Research Execution | FUTURE | (TBD) | Research brief | sources rows |
| P3 | Script Generation | BUILT | script\_generator.py | Manual brief / sources | hook \+ body JSON |
| P3b | Segmentation | BUILT | segmentation.py | scripts row | asset\_briefs rows |
| P4 | Mechanic Extraction | BUILT | mechanic\_extractor.py | segment text | game/mechanic/moment per segment |
| P4b | Asset Sourcing | BUILT | asset\_sourcer.py \+ reference\_manager.py | asset\_briefs rows | selected assets \+ reference images |
| P4c | YouTube Clip Sourcing | DISABLED | youtube\_sourcer.py | search queries | clip files |
| P4d | Wiki Asset Sourcing | NEW v0.6 | wiki\_sourcer.py | game\_title \+ mechanic | wiki images \+ reference candidates |
| P5 | Prompt Building | BUILT | prompt\_builder.py | game/mechanic/moment | prompts \+ drawtext strings |
| P6 | Voice Synthesis | BUILT | Edge TTS | Approved script | hook.mp3 \+ body.mp3 |
| P7 | Video Assembly | BUILT | assembler.py \+ FFmpeg | assets \+ audio | output/video\_N.mp4 \+ SRT |
| P8 | Package Output | PLANNED | (TBD) | Completed video | Upload-ready package |
| P9 | Publishing | FUTURE | (TBD) | Package | Published URL |

# **4\. New Modules (v0.6)**

## **4.1 core/wiki\_sourcer.py**

Handles all Fandom wiki interactions. Searches for game pages, retrieves images, extracts mechanic content. Used by reference\_manager.py for reference image acquisition and by P2 (future) for research content.

| search\_game\_page(game\_title) | Queries Fandom API: https://{slug}.fandom.com/api.php. Returns page content and image list for best matching page. Timeout: 10s. |
| :---- | :---- |
| **get\_page\_images(page\_title, game\_slug)** | Returns list of image URLs from a wiki page ordered by resolution descending. Filters out icons \< 200px. |
| **download\_image(url)** | Downloads image bytes. Validates minimum dimensions (800px width). Returns bytes or None. |
| **find\_game\_slug(game\_title)** | Converts game title to Fandom slug. 'Cookie Clicker' → 'cookieclicker'. Tries common patterns, falls back to search. |
| **get\_mechanic\_content(game\_title, mechanic)** | Returns plain text content from wiki page most relevant to mechanic keyword. For P2 research use. |

Forbidden dependencies:

| FORBIDDEN | DB writes, LLM calls, FFmpeg calls, asset\_sourcer calls, prompt building |
| :---- | :---- |
| **Returns** | bytes (image) or str (content) or None on failure |
| **Timeout policy** | 10s per request. Never block pipeline on wiki failure. |

## **4.2 core/reference\_manager.py**

Manages the reference image lifecycle for each game. Acquires references via priority chain, stores them in assets/references/, and updates game\_clip\_index. Called by asset\_sourcer before generate\_image().

| get\_reference(game\_title) | Returns reference image bytes for a game. Checks game\_clip\_index first. If reference\_image\_path exists and file is valid: return bytes. If not: call acquire\_reference(). |
| :---- | :---- |
| **acquire\_reference(game\_title)** | Priority chain: (1) wiki\_sourcer → Fandom API. (2) clip frame extraction via ffmpeg from any clip in game\_clip\_index. (3) Google Images search via googlesearch-python. (4) Flag for Director — write needs\_reference=1 to game\_clip\_index, return None. |
| **store\_reference(game\_title, image\_bytes)** | Saves to assets/references/{game\_slug}.png. Updates game\_clip\_index.reference\_image\_path. Validates minimum 800px width before storing. |
| **extract\_clip\_frame(clip\_path)** | ffmpeg subprocess: extract frame at 10% duration. Returns bytes. Used as fallback when wiki fails. |
| **flag\_for\_director(game\_title)** | Writes needs\_reference=1 to game\_clip\_index. Pipeline continues without reference — generates without grounding. |

Forbidden dependencies:

| FORBIDDEN | LLM calls, prompt building, assembler calls, script generation |
| :---- | :---- |
| **Storage** | assets/references/{game\_slug}.png |
| **Reuse** | Once acquired, reference is reused for all future videos mentioning that game. Never re-acquired unless file is missing or corrupt. |

# **5\. Image Cycling System (ADR-009)**

Every segment longer than image\_cycling\_interval\_s seconds cycles through multiple images rather than holding a single image. This prevents static visual holds and maintains viewer attention.

## **5.1 Cycling Modes**

| ken\_burns (default) | Single image generated per segment. Assembler applies varied Ken Burns per interval: alternating zoom-in/zoom-out, varied pan direction seeded by segment index. Zero extra API calls. Subtle but effective for intervals under 20s. |
| :---- | :---- |
| **variants (optional)** | Multiple images generated per segment. N \= ceil(estimated\_duration\_s / image\_cycling\_interval\_s). Each image uses a varied prompt: base prompt \+ one variation modifier. Assembler cycles through generated images. Costs N API calls per segment. |

## **5.2 Variant Prompt Generation**

When cycling\_mode=variants, prompt\_builder.py generates N prompts per segment:

* Prompt 1 (base): '{game\_title} {moment} digital art, vibrant game UI screenshot style, 4K'

* Prompt 2 (variant): '{game\_title} {moment} close-up detail, vibrant game UI screenshot style, 4K'

* Prompt 3 (variant): '{game\_title} {moment} wide establishing shot, vibrant game UI screenshot style, 4K'

| Variation modifiers pool | close-up detail | wide establishing shot | from above | dramatic angle | UI focus | ambient lighting | action moment |
| :---- | :---- |
| **Selection** | Modifiers selected by segment\_index % len(modifiers) for reproducibility |
| **Max variants** | 3 — never generate more than 3 per segment regardless of duration |

*NOTE: Ken Burns variation is always applied regardless of cycling mode. Even in variants mode, each image gets unique Ken Burns parameters.*

## **5.3 Config Flags**

| image\_cycling\_enabled | Boolean. Default: true. |
| :---- | :---- |
| **image\_cycling\_mode** | ken\_burns | variants. Default: ken\_burns. |
| **image\_cycling\_interval\_s** | Integer. Default: 12\. Max seconds per image before cycling. |
| **image\_variant\_count** | Integer. Default: 2\. Max variants when mode=variants. Range: 2-3. |
| **reference\_images\_enabled** | Boolean. Default: true. |

# **6\. Subtitle System**

Subtitles are generated from actual audio output via Whisper, not from the script text. This ensures timestamps match what Edge TTS actually produced, not estimated word counts.

| Step 1 — Audio assembly | hook.mp3 \+ body.mp3 concatenated into full\_audio.mp3 by assembler before segment stitching |
| :---- | :---- |
| **Step 2 — Whisper transcription** | openai-whisper runs on full\_audio.mp3. Output: word-level timestamps as JSON. Model: base (fast, accurate enough for clean TTS audio) |
| **Step 3 — SRT generation** | Python converts Whisper JSON to SRT format. Saved as output/video\_N.srt |
| **Step 4 — Burn or sidecar** | subtitle\_mode=srt: SRT file only. subtitle\_mode=burn: FFmpeg subtitles filter applied. subtitle\_mode=both: both outputs produced |

| Default | subtitles\_enabled: false, subtitle\_mode: srt |
| :---- | :---- |
| **Whisper model** | base — fast and accurate for synthetic TTS. Upgrade to small if accuracy issues arise. |
| **SRT location** | output/video\_N.srt alongside video\_N.mp4 |
| **Upload note** | YouTube accepts SRT sidecar files for manual caption upload. Default SRT-only avoids burned-in text quality loss. |

# **7\. Reference Image Flow**

Complete flow from game title to grounded image generation:

| 1\. Mechanic extraction (P4) | game\_title identified from segment text by mechanic\_extractor.py |
| :---- | :---- |
| **2\. Reference lookup** | asset\_sourcer calls reference\_manager.get\_reference(game\_title) |
| **3a. Cache hit** | reference\_image\_path exists in game\_clip\_index and file is valid → return bytes immediately |
| **3b. Fandom API** | wiki\_sourcer.search\_game\_page() → get\_page\_images() → download highest resolution image → validate → store |
| **3c. Clip frame fallback** | Any clip in game\_clip\_index for this game → ffmpeg frame extraction at 10% duration → validate → store |
| **3d. Google Images fallback** | googlesearch-python query: '{game\_title} gameplay screenshot' → first result → download → validate → store |
| **3e. Director flag** | All sources failed → needs\_reference=1 in game\_clip\_index → generate\_image() called without reference |
| **4\. Generate with reference** | llm\_client.generate\_image(prompt, reference\_bytes) → multimodal request to Gemini flash image → image bytes |
| **5\. Store asset** | asset\_sourcer saves to assets/generated/seg\_{N}\_{ts}.png → writes path to asset\_briefs.selected\_asset |

# **8\. Schema Changes (v0.6)**

## **8.1 game\_clip\_index additions**

| Field | Type | Description |
| :---- | :---- | :---- |
| reference\_image\_path | TEXT NULL | Path to stored reference image. assets/references/{slug}.png |
| needs\_reference | INTEGER DEFAULT 0 | Flag: 1 \= all acquisition sources failed, Director must provide manually |

## **8.2 asset\_briefs additions**

| Field | Type | Description |
| :---- | :---- | :---- |
| image\_paths | TEXT NULL | JSON array of asset paths for cycling. Single item when ken\_burns mode. |
| image\_variant\_count | INTEGER DEFAULT 1 | Number of images generated for this segment |
| reference\_used | INTEGER DEFAULT 0 | Boolean: 1 if reference image was used in generation |

## **8.3 render\_jobs (confirm existing fields)**

| Field | Type | Description |
| :---- | :---- | :---- |
| subtitle\_mode | TEXT NULL | srt | burn | both. Null when subtitles\_enabled=false |
| srt\_path | TEXT NULL | Path to generated SRT file. Populated when subtitles generated. |

# **9\. Module Contracts Update**

| core/wiki\_sourcer.py (NEW) | Responsibility: Fandom API search, image retrieval, mechanic content extraction. Forbidden: DB writes, LLM calls, FFmpeg, prompt building, asset\_sourcer calls. |
| :---- | :---- |
| **core/reference\_manager.py (NEW)** | Responsibility: Reference image lifecycle — acquire, store, retrieve. Forbidden: LLM calls, prompt building, assembler calls, script generation. |
| **core/prompt\_builder.py (UPDATED)** | Add: build\_variant\_prompts(game\_title, mechanic, moment, n) → list\[str\]. Pure function. No external dependencies. |
| **core/asset\_sourcer.py (UPDATED)** | Add: call reference\_manager.get\_reference() before generate\_image(). Pass reference bytes to llm\_client.generate\_image(). |
| **core/llm\_client.py (UPDATED)** | Add: reference\_bytes optional param to generate\_image(). Send as base64 image in multimodal message content when provided. |
| **core/assembler.py (UPDATED)** | Add: Ken Burns cycling logic per segment using image\_paths JSON array. Varied pan/zoom per image in cycle. Whisper SRT generation when subtitles\_enabled. |
| **core/index\_manager.py (UPDATED)** | Add: reference\_image\_path and needs\_reference column management. |

# **10\. Architectural Decision Records**

| ADR-001 | Manual Brief Mode. Permanent supported input mode. Bypasses P1/P2. |
| :---- | :---- |
| **ADR-002** | Dual-Format Script JSON Contract. hook \+ body as separate fields. |
| **ADR-003** | SQLite WAL. Unconditional at DB init. |
| **ADR-004** | Unified OpenRouter LLM Client. All LLM and image generation via single client. |
| **ADR-005** | Transcript-First Visual Assembly. Paragraph boundaries define segment cuts. |
| **ADR-006** | YouTube Clip Sourcing. yt-dlp \+ LLM judge. Disabled in MVP. |
| **ADR-007** | SoC/SRP Enforcement. No module contains another module's logic. |

| ADR-008 | Reference Image Grounding |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | AI image generation without visual grounding produces stylistically inconsistent images that may not match the actual game aesthetic. Cookie Clicker has a specific pixel art style; Adventure Capitalist has a specific cartoon style. Ungrounded generation risks producing images that misrepresent the games being discussed. |
| **Decision** | Every game referenced in a script has a reference image stored in assets/references/. Reference images are acquired automatically via priority chain: (1) Fandom wiki API — highest resolution page image. (2) Clip frame extraction — ffmpeg frame from any accepted clip for that game. (3) Google Images — first result for '{game} gameplay screenshot'. (4) Director flag — needs\_reference=1, generation continues without reference. Reference is stored once and reused across all future videos for that game. |
| **Consequences** | Generated images are visually grounded to actual game aesthetics. Reference acquisition is fully automated with no Director intervention required in most cases. One-time acquisition cost per game title, zero cost on reuse. Storage: assets/references/ directory, one PNG per game. |
| **Rejected** | Manual reference provision: requires Director time per game. Generation without reference: produces inconsistent results as proven in first video session. |

| ADR-009 | Image Cycling |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | Single images held for 20–39 seconds produce a static, low-quality visual experience. Viewers expect visual variety. The first complete video validated the pipeline but identified static image holds as the primary quality improvement needed. |
| **Decision** | All segments cycle visuals at maximum image\_cycling\_interval\_s (default: 12s). Two modes: (1) ken\_burns — single generated image with varied Ken Burns parameters per interval. Zero extra API calls. Default mode. (2) variants — multiple images generated with varied prompts. N \= ceil(duration / interval), max 3\. Optional, toggled via config. Ken Burns variation is always applied regardless of mode. Mode is configurable per video run via config.yaml. |
| **Consequences** | No image held longer than 12 seconds by default. Ken Burns mode adds zero cost. Variant mode adds N-1 extra image generation calls per long segment. Visual variety significantly improves retention without requiring YouTube clip sourcing. |
| **Rejected** | Fixed Ken Burns on single image for full segment duration: viewer fatigue on segments over 15s. Full variant generation always: unnecessary cost for short segments under 12s. |

# **11\. Open Questions**

| OQ-001 — ACTIVE | P2 web search API: Brave Search vs alternatives. |
| :---- | :---- |
| **OQ-003** | Channel identity: separate from rfditservices.com or linked? |
| **OQ-004** | Content cadence target. |
| **OQ-005** | GDC Vault free tier access. |
| **OQ-007** | Voice identity: GuyNeural flagged as generic. Kokoro TTS evaluation deferred. |
| **OQ-008** | yt-dlp YouTube rate limiting at volume. |
| **OQ-009** | YouTube Data API v3 OAuth2 for P9 publishing. |
| **OQ-010** | Short format assembly: hook only or hook \+ one body segment? |
| **OQ-011 — NEW** | googlesearch-python reliability: Google actively blocks automated search. May need SerpAPI free tier as fallback for Google Images acquisition. Monitor on first reference acquisition run. |
| **OQ-012 — NEW** | Whisper model size: base model sufficient for Edge TTS synthetic audio? Upgrade to small if word-level timestamp accuracy is insufficient for subtitle sync. |

# **12\. Next Steps**

* Directive 1: wiki\_sourcer.py \+ reference\_manager.py — new modules with tests

* Directive 2: llm\_client.py \+ asset\_sourcer.py — wire reference into generation

* Directive 3: assembler.py — Ken Burns cycling \+ Whisper SRT generation

* Full pipeline run with reference images and cycling enabled

* Resolve OQ-003 — channel identity before first public video

* Resolve OQ-007 — voice identity before first public video

*ContentEngine SDD v0.6  —  RFD IT Services Ltd.  —  April 2026*
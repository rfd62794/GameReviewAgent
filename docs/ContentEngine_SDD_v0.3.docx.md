**ContentEngine**

Software Design Document v0.3

*AI-Powered YouTube Content Pipeline*

April 2026  —  RFD IT Services Ltd.

*v0.3 adds: P3b Transcript Segmentation • P4 Asset Sourcing • P7 FFmpeg Assembly • ADR-005*

# **Revision History**

| v0.1 — Apr 2026 | Initial SDD. 7-phase pipeline, dual-format output, SQLite storage, OpenRouter LLM routing. |
| :---- | :---- |
| **v0.2 — Apr 2026** | ADR-001 Manual Brief Mode. ADR-002 Dual-Format JSON contract. ADR-003 SQLite WAL. Asset briefs default to screen recording directives. Phase map reordered. |
| **v0.3 — Apr 2026** | ADR-004 Unified OpenRouter client (Tier 3). ADR-005 Visual Assembly Pipeline. P3b Transcript Segmentation added. P4 Asset Sourcing expanded (Pexels \+ Wikimedia \+ local gameplay \+ AI image). P7 FFmpeg Assembly stage added with subtitle toggle. Pipeline updated to transcript-first asset timing. Edge TTS confirmed as zero-cost P6 voice layer. |

# **1\. Purpose & Scope**

ContentEngine is a standalone Python pipeline for generating, researching, and packaging short-form YouTube content. It operates as an AI-assisted production system with a human director at the top of the execution model.

The primary output is dual-format video content: mid-form explainers (3–5 minutes) and repurposed Shorts (\<60 seconds), both built from the same research brief and script. The initial content domain is game mechanics and game design analysis.

As of v0.3, the pipeline produces a complete MP4 video output from a text brief, with no manual assembly required.

# **2\. System Architecture**

## **2.1 Execution Model**

ContentEngine follows the established three-layer model:

* Director (Robert) — picks topic, sets angle, approves script, approves final output

* Pipeline (ContentEngine) — research, script generation, asset sourcing, assembly

* Coding Agent (Antigravity) — implements pipeline stages per directive

## **2.2 Full Pipeline Stages**

As of v0.3, the complete pipeline from brief to MP4:

| Phase | Name | Responsibility | Output |
| :---- | :---- | :---- | :---- |
| P1 | Brief Generation | AI (DeepSeek via OpenRouter) | topic\_briefs row — BYPASSED in Manual Mode |
| P2 | Research Execution | AI \+ Web Sources | sources rows — BYPASSED in Manual Mode |
| P3 | Script Drafting | Claude Sonnet-4-6 via OpenRouter | JSON: hook\_short\_script \+ mid\_form\_body (ADR-002) |
| P3b | Transcript Segmentation | Python — no LLM | Paragraph-boundary segments with visual\_type tags, written to asset\_briefs |
| P4 | Asset Sourcing | Pexels API \+ Wikimedia API \+ local gameplay library \+ AI image gen | assets/ directory: stills, clips, AI images keyed to segment index |
| P4b | Asset Selection | Python — relevance scoring | Ranked asset list per segment, written to asset\_briefs.selected\_asset |
| P6 | Voice Synthesis | Edge TTS — zero cost | audio/hook.mp3 \+ audio/body.mp3 |
| P7 | FFmpeg Assembly | FFmpeg \+ Python orchestration | output/video.mp4 — Ken Burns on stills, direct play on clips, optional SRT |

## **2.3 Transcript-First Asset Timing (ADR-005)**

Asset sourcing runs from the written transcript, not the audio file. Paragraph boundaries in the script define segment cuts. This allows P4 asset sourcing to run in parallel with P6 audio generation, reducing total pipeline time.

| Segment boundary | Each paragraph in mid\_form\_body is one segment. Hook is always segment 0\. |
| :---- | :---- |
| **Target duration per segment** | Word count of segment ÷ 2.8 wps \= estimated seconds. Used to determine clip length or Ken Burns duration. |
| **Visual type assignment** | P3b assigns visual\_type per segment: gameplay\_clip | stock\_still | stock\_clip | ai\_image. Logic based on segment content keywords. |
| **Parallel execution** | P4 and P6 are independent. Both read from scripts table. No dependency between them until P7. |

## **2.4 Dual-Format Script Contract (ADR-002)**

Scripts are generated as a structured JSON object with hook\_short\_script and mid\_form\_body as separate fields. The LLM prompt contract forbids the body from referencing the hook. Concatenation for mid-form is programmatic.

## **2.5 Visual Assembly Strategy (ADR-005)**

Motion style is mixed based on asset type. Ken Burns pan/zoom is applied to all stills. Clips play at native speed. Transitions are hard cuts by default — crossfade available as config option.

| Stills (Pexels, Wikimedia, AI) | Ken Burns effect — slow zoom or pan, direction randomised per asset |
| :---- | :---- |
| **Stock clips (Pexels video)** | Direct play, trimmed to segment duration |
| **Gameplay clips (local library)** | Direct play, trimmed to segment duration |
| **Transitions** | Hard cut default. config.yaml: transition\_style: hard | crossfade |
| **Subtitles** | Toggle in config.yaml: subtitles\_enabled: false (default). When true: SRT generated via Whisper from audio, burned into video or exported as separate .srt file (subtitle\_mode: burn | srt | both) |

# **3\. Data Model**

## **3.1 Storage**

All persistent state in content\_engine.db (SQLite, WAL enabled per ADR-003). Schema version: SCHEMA\_VERSION constant, checked at startup.

## **3.2 Core Tables**

### **topics**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| title | TEXT | Human-readable topic label |
| domain | TEXT | game\_mechanics | game\_design | indie\_dev |
| input\_mode | TEXT | topic\_only | topic\_angle | topic\_notes | manual\_brief |
| angle | TEXT NULL | Director-supplied angle or null |
| notes | TEXT NULL | Director-supplied rough notes or null |
| status | TEXT | queued | researching | scripting | ready | published |
| created\_at | TEXT | ISO 8601 |
| updated\_at | TEXT | ISO 8601 |

### **scripts**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| topic\_id | INTEGER FK | References topics.id |
| version | INTEGER | Increments on regeneration |
| hook\_short\_script | TEXT | Self-contained Short segment. 90–120 words. |
| mid\_form\_body | TEXT | Body content only. Concatenated with hook for mid-form render. |
| word\_count\_hook | INTEGER | Word count of hook segment |
| word\_count\_body | INTEGER | Word count of body segment |
| estimated\_duration\_s | INTEGER | Total mid-form estimated duration in seconds |
| title\_suggestion | TEXT | YouTube title suggestion ≤ 60 chars |
| tags | TEXT | JSON array of 5–8 keyword strings |
| approved | INTEGER | Boolean — director approval flag |
| created\_at | TEXT | ISO 8601 |

### **asset\_briefs**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| script\_id | INTEGER FK | References scripts.id |
| segment\_index | INTEGER | Script segment index (0 \= hook) |
| segment\_text | TEXT | Raw text of this segment |
| estimated\_duration\_s | INTEGER | Segment word count ÷ 2.8 wps |
| visual\_type | TEXT | gameplay\_clip | stock\_still | stock\_clip | ai\_image |
| search\_query | TEXT | Generated search query for Pexels/Wikimedia |
| ai\_image\_prompt | TEXT NULL | Image generation prompt if visual\_type=ai\_image |
| selected\_asset | TEXT NULL | Path to chosen asset file |
| asset\_source | TEXT NULL | pexels | wikimedia | local | ai\_generated |
| status | TEXT | pending | sourced | approved |

### **render\_jobs**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| script\_id | INTEGER FK | References scripts.id |
| format | TEXT | mid\_form | short |
| subtitles\_enabled | INTEGER | Boolean from config at render time |
| subtitle\_mode | TEXT NULL | burn | srt | both — null if subtitles disabled |
| output\_path | TEXT NULL | Path to completed MP4 |
| status | TEXT | queued | assembling | complete | failed |
| created\_at | TEXT | ISO 8601 |
| completed\_at | TEXT NULL | ISO 8601 |

# **4\. Asset Sourcing Layer**

## **4.1 Source Registry**

| Pexels API | Free tier: 200 requests/hour. Stills and video clips. No attribution required. Primary source for abstract and concept visuals. API key required (free). |
| :---- | :---- |
| **Wikimedia Commons** | Free, no key required. Game screenshots, UI captures, official artwork. Primary source for game-specific visuals. Rate limit: 200 req/s with User-Agent header. |
| **Local Gameplay Library** | Director-captured screen recordings stored in assets/gameplay/. Indexed by game\_title tag. P4 checks local library before calling APIs. |
| **AI Image Generation** | Free tier options: Pollinations.ai (no key, HTTP API), Craiyon API (free tier). Used for abstract concept segments where no stock visual fits. Prompt generated by P3b from segment text. |

## **4.2 Asset Selection Logic**

P4b scores candidate assets per segment and selects the best match. Selection priority:

* Local gameplay clip — highest priority for game-specific segments

* Wikimedia game screenshot — for named game references

* Pexels video clip — for concept segments with motion

* Pexels still — for concept segments, Ken Burns applied

* AI generated image — fallback for abstract concepts with no stock match

*NOTE: Minimum one asset per segment is enforced. P7 will not assemble if any segment has status=pending.*

# **5\. Assembly Layer (P7)**

## **5.1 FFmpeg Orchestration**

P7 generates a Python-orchestrated FFmpeg command sequence. No manual editing required. Assembly is fully deterministic from asset\_briefs and render\_jobs tables.

| Ken Burns implementation | FFmpeg zoompan filter. Direction (zoom-in vs zoom-out, pan direction) randomised per asset via seeded RNG for reproducibility. |
| :---- | :---- |
| **Clip trimming** | FFmpeg \-t flag. Duration from asset\_briefs.estimated\_duration\_s. |
| **Audio sync** | Hook audio prepended to body audio via FFmpeg concat. Single audio track. |
| **Subtitle generation** | Whisper (openai-whisper, local, free) transcribes assembled audio. Output as .srt. Burned via FFmpeg subtitles filter if subtitle\_mode=burn. |
| **Output format** | MP4, H.264 video, AAC audio. 1080x1920 for Shorts, 1920x1080 for mid-form. Config-driven. |
| **Short assembly** | Hook segment only. assets for segment\_index=0 plus hook audio. |

## **5.2 Config Flags (config.yaml additions)**

| subtitles\_enabled | Boolean. Default: false. |
| :---- | :---- |
| **subtitle\_mode** | burn | srt | both. Only read if subtitles\_enabled: true. |
| **transition\_style** | hard | crossfade. Default: hard. |
| **output\_resolution\_midform** | Default: 1920x1080 |
| **output\_resolution\_short** | Default: 1080x1920 |
| **ken\_burns\_intensity** | slow | medium | fast. Controls zoompan speed. Default: slow. |
| **asset\_fallback\_ai** | Boolean. Whether to use AI image generation as fallback. Default: true. |

# **6\. External Tooling**

| Script Generation (P3) | claude-sonnet-4-6 via OpenRouter (ADR-004) |
| :---- | :---- |
| **Research / Brief (P1)** | deepseek/deepseek-chat via OpenRouter — Phase 2+ |
| **Web Research (P2)** | Brave Search API — Phase 2+. See OQ-001. |
| **Voice Synthesis (P6)** | Edge TTS — zero cost, no account. en-US-GuyNeural default. |
| **Asset Sourcing** | Pexels API (free key) \+ Wikimedia (no key) \+ local library |
| **AI Image Generation** | Pollinations.ai (no key) or Craiyon (free tier) |
| **Video Assembly** | FFmpeg — local, free, Python subprocess orchestration |
| **Subtitle Transcription** | openai-whisper — local, free, Python library |
| **Storage** | SQLite \+ WAL. Python sqlite3 stdlib. |
| **Config** | config.yaml — consistent with OpenAgent pattern |
| **LLM Routing** | Single OpenRouter client ported from OpenAgent (ADR-004) |

# **7\. Development Phase Map**

| Phase | Name | Responsibility | Output |
| :---- | :---- | :---- | :---- |
| Phase 1 | Reverse Pipeline Validation | Manual Brief → P3 Script → P6 Audio. SQLite \+ WAL. AGENT\_CONTRACT. 54 tests passing. | COMPLETE ✔ |
| Phase 1b | Prompt Contract Tuning | VOICE & RHYTHM constraints added. Shorter sentences, banned academic phrases, opinion required. | COMPLETE ✔ |
| Phase 2 | Visual Assembly | P3b Transcript Segmentation \+ P4 Asset Sourcing \+ P4b Selection \+ P7 FFmpeg Assembly \+ subtitle toggle | Current target |
| Phase 3 | Automated Research | P1 Brief Generation \+ P2 Research Execution \+ Brave Search API | Deferred — post Phase 2 |
| Phase 4 | CLI & Queue | Topic queue, batch runs, full CLI interface | Deferred |
| Phase 5 | Automation & Scheduling | Scheduled runs, output monitoring, cadence tracking | Deferred |

# **8\. Architectural Decision Records**

## **ADR-001: Pipeline Validation via Manual Brief Mode**

| ADR-001 | Pipeline Validation via Manual Brief Mode |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Decision** | Phase 1 exclusively implements Manual Brief Mode. Handcrafted JSON brief passes directly to P3. Automated research deferred to Phase 3\. |
| **Consequences** | Output quality validated before research automation is built. Manual Brief Mode is a permanent supported input mode. |

## **ADR-002: Dual-Format Script JSON Contract**

| ADR-002 | Dual-Format Script JSON Contract |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Decision** | P3 LLM prompt enforces JSON with hook\_short\_script (90–120 words, self-contained) and mid\_form\_body (400–650 words, no hook dependency). Concatenation is programmatic. |
| **Consequences** | Shorts render from hook field alone. Mid-form assembled deterministically. Test anchors validate JSON structure before audio. |

## **ADR-003: SQLite WAL Configuration**

| ADR-003 | SQLite WAL Configuration |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Decision** | PRAGMA journal\_mode=WAL; executed unconditionally at DB init. No override. |
| **Consequences** | Concurrent readers and writers during background generation tasks. No lockouts. |

## **ADR-004: Unified OpenRouter LLM Client**

| ADR-004 | Unified OpenRouter LLM Client |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Decision** | All LLM calls routed through single OpenRouter client ported from OpenAgent. Model strings in config/models.yaml. Direct Anthropic SDK deferred as volume optimisation. |
| **Consequences** | Single API key, single HTTP client, single code path. Minor per-call cost premium vs direct API accepted at MVP volume. |

## **ADR-005: Transcript-First Visual Assembly**

| ADR-005 | Transcript-First Visual Assembly |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | Timing visuals to audio after generation requires sequential execution and Whisper analysis of every asset change. Timing visuals to the written transcript allows parallel execution and is more predictable. |
| **Decision** | Paragraph boundaries in the script define visual segment cuts. P3b runs immediately after P3, segmenting the transcript and assigning visual types. P4 asset sourcing and P6 audio generation run in parallel. P7 assembly waits for both. Whisper is used only for subtitle generation, not for timing. |
| **Visual motion** | Ken Burns pan/zoom on all stills. Direct play on all clips. Mixed per asset type. Transition style config-driven, default hard cut. |
| **Subtitle toggle** | subtitles\_enabled in config.yaml, default false. When true: Whisper transcribes assembled audio, output as SRT and/or burned per subtitle\_mode flag. |
| **Asset sources** | Pexels API (stills \+ clips) \+ Wikimedia Commons (game screenshots) \+ local gameplay library (director-captured) \+ AI image generation (Pollinations.ai / Craiyon) for abstract concept fallback. |
| **Consequences** | P4 and P6 parallelisable. Assembly is fully deterministic. Subtitle generation is optional and isolated. Asset sourcing is extensible by adding new source handlers without touching P7. |

# **9\. Open Questions**

| OQ-001 — ACTIVE | Web search API for P2 (Phase 3+): Brave Search preferred pending cost review. |
| :---- | :---- |
| **OQ-002 — RESOLVED** | Dual-format script separation. Resolved by ADR-002. |
| **OQ-003** | Channel name and identity: separate from rfditservices.com or linked? |
| **OQ-004** | Content cadence target: affects queue depth and pipeline throughput planning. |
| **OQ-005** | GDC Vault free tier access limitations. Confirm before Phase 3 research layer. |
| **OQ-006 — NEW** | AI image generation quality: Pollinations.ai vs Craiyon vs local Stable Diffusion. Evaluate on first abstract segment before committing to a provider. |
| **OQ-007 — NEW** | Voice identity: GuyNeural accepted as MVP but flagged as generic. Evaluate Kokoro TTS or custom Edge TTS voice for publishing identity. |

# **10\. Next Steps**

* Phase 2 directive to Antigravity: P3b \+ P4 \+ P4b \+ P7

* Pexels API key — free registration required before P4 runs

* FFmpeg confirmed installed on dev machine — verify before P7 directive

* Resolve OQ-006 — test Pollinations.ai on one abstract segment before P4 is built

* Local gameplay library — capture Cookie Clicker and Adventure Capitalist footage for first video

* Resolve OQ-007 post-Phase 2 — voice identity decision before publishing

*ContentEngine SDD v0.3  —  RFD IT Services Ltd.  —  April 2026*
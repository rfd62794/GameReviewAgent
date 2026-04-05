**ContentEngine**

Software Design Document v0.5

*AI-Powered YouTube Content Pipeline — Definitive Edition*

April 2026  —  RFD IT Services Ltd.

*Supersedes v0.1–v0.4. Introduces complete stage plan, Section 11 Module Contracts, SoC/SRP refactor targets.*

# **1\. Revision History**

| v0.1 | Initial SDD. 7-phase pipeline, dual-format output, SQLite, OpenRouter. |
| :---- | :---- |
| **v0.2** | ADR-001/002/003. Manual Brief Mode. Dual-format JSON contract. WAL. |
| **v0.3** | ADR-004/005. OpenRouter unified client. Transcript-first visual assembly. Edge TTS confirmed. |
| **v0.4** | ADR-006. YouTube clip sourcing via yt-dlp \+ LLM relevance judgment. Game clip index. |
| **v0.5 — Apr 2026** | Definitive edition. Complete 9-stage pipeline plan covering MVP through future phases. Section 11 Module Contracts. SoC/SRP violation inventory. Naming convention locked. stage\_p\*.py structure established. |

# **2\. Purpose & Scope**

ContentEngine is a standalone Python pipeline for generating, researching, and packaging short-form YouTube content. It operates as an AI-assisted production system with a human director at the top of the execution model.

As of v0.5, the pipeline is defined across 9 stages covering the full lifecycle from topic brief to published video. MVP stages (P3–P7) are built. Research stages (P1–P2) and publishing stages (P8–P9) are planned for future phases.

This document supersedes all previous SDD versions. It is the authoritative reference for architecture, stage contracts, module responsibilities, and ADRs.

# **3\. Pipeline Summary**

All 9 stages at a glance. Status codes: BUILT \= production ready. NEEDS REFACTOR \= built but SoC violations present. PLANNED \= specced, not built. FUTURE \= concept only. DISABLED \= built but config-gated.

| Code | Name | Status | Core Module(s) | Input | Output |
| :---- | :---- | :---- | :---- | :---- | :---- |
| P1 | Brief Generation | FUTURE | (TBD — DeepSeek) | Director topic input | Structured research brief |
| P2 | Research Execution | FUTURE | (TBD — Brave Search API) | Research brief | sources table rows |
| P3 | Script Generation | BUILT | script\_generator.py | Approved brief / manual JSON | hook \+ body JSON in scripts table |
| P3b | Segmentation | NEEDS REFACTOR | segmentation.py | scripts table row | asset\_briefs rows |
| P4 | Mechanic Extraction | NEEDS REFACTOR | mechanic\_extractor.py | segment text | game, mechanic, moment per segment |
| P4b | Asset Sourcing | NEEDS REFACTOR | asset\_sourcer.py | asset\_briefs rows | selected\_asset paths |
| P4c | YouTube Clip Sourcing | DISABLED | youtube\_sourcer.py | search queries \+ segment text | clip file in assets/clips/ |
| P5 | Prompt Building | PLANNED | prompt\_builder.py (new) | game, mechanic, moment, segment\_text | Pollinations prompt \+ drawtext string |
| P6 | Voice Synthesis | BUILT | stage\_p6\_audio.py \+ Edge TTS | Approved script | audio/hook.mp3 \+ audio/body.mp3 |
| P7 | Video Assembly | NEEDS REFACTOR | assembler.py \+ FFmpeg | asset paths \+ audio \+ durations | output/video\_N.mp4 |
| P8 | Package Output | PLANNED | (TBD) | Completed video \+ metadata | Upload-ready package |
| P9 | Publishing | FUTURE | (TBD — YouTube Data API) | Package | Published video URL |

# **4\. Execution Model**

ContentEngine follows the established three-layer model:

* Director (Robert) — picks topic, sets angle, approves script, approves final output

* Pipeline (ContentEngine) — all stages P1–P9 orchestrated by pipeline\_run.py

* Coding Agent (Antigravity) — implements stages per directive, never architects

| Master entry point | pipeline\_run.py — calls stage runners in sequence, passes topic\_id and config |
| :---- | :---- |
| **Stage runners** | stage\_p\*.py — thin orchestrators. Load from DB, call core modules, write to DB. No business logic. |
| **Core modules** | core/\*.py — single responsibility each. See Section 11 for contracts. |
| **Config** | config.yaml — read once at pipeline init. Passed to stages as needed. |
| **State** | content\_engine.db (SQLite \+ WAL) — all persistent state. No in-memory passing between stages. |

# **5\. Stage Detail**

Each stage defined with: inputs, outputs, core modules called, success condition, failure/fallback, SoC violations to resolve, and forbidden dependencies.

**P1 — Brief Generation \[FUTURE\]**  
*Runner: stage\_p1\_brief.py (not yet created)*

| Inputs | Director-provided topic string \+ angle \+ input\_mode from CLI |
| :---- | :---- |
| **Outputs** | topic\_briefs table row with structured research brief JSON |
| **Core Modules Called** | llm\_client.py (DeepSeek via OpenRouter) |
| **Success Condition** | LLM retry up to 3 times. On all failures: write status=failed to topics table, halt stage, notify director. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Web search calls — those belong to P2 |
| :---- |
| ✗  Asset sourcing or script generation logic |
| ✗  Display logic or terminal formatting |

*NOTE: P1 is bypassed entirely when input\_mode=manual\_brief. Manual Brief Mode is a permanent supported path per ADR-001.*

**P2 — Research Execution \[FUTURE\]**  
*Runner: stage\_p2\_research.py (not yet created)*

| Inputs | topic\_briefs row from P1 output |
| :---- | :---- |
| **Outputs** | sources table rows — one per retrieved source, with summary and source\_type |
| **Core Modules Called** | llm\_client.py (DeepSeek) \+ web\_searcher.py (Brave Search API — not yet built) |
| **Success Condition** | On web search API failure: log error, attempt with cached sources if available. On zero sources: halt, notify director. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Script generation logic |
| :---- |
| ✗  Asset sourcing |
| ✗  LLM calls beyond summarisation |

*NOTE: OQ-001: Brave Search API vs alternatives unresolved. Must be decided before P2 implementation begins.*

**P3 — Script Generation \[BUILT\]**  
*Runner: stage\_p3\_script.py*

| Inputs | topic\_id \+ approved brief (manual JSON or sources table rows) |
| :---- | :---- |
| **Outputs** | scripts table row: hook\_short\_script, mid\_form\_body, word counts, title\_suggestion, tags, approved=0 |
| **Core Modules Called** | llm\_client.py (claude-sonnet-4-6 via OpenRouter) \+ script\_generator.py |
| **Success Condition** | LLM retry up to 3 attempts. Each attempt validates full JSON contract. On 3 failures: halt, print last validation error. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Segmentation logic |
| :---- |
| ✗  Asset sourcing or prompt building |
| ✗  Audio or video generation |

Current violations: None. P3 is clean.

**P3b — Transcript Segmentation \[NEEDS REFACTOR\]**  
*Runner: stage\_p3b\_segment.py*

| Inputs | Approved scripts table row (script\_id) |
| :---- | :---- |
| **Outputs** | asset\_briefs table rows — one per paragraph segment. Fields: segment\_index, segment\_text, estimated\_duration\_s. Does NOT set visual\_type. |
| **Core Modules Called** | segmentation.py only |
| **Success Condition** | On empty script: halt with error. On single-paragraph script: one segment row written, continue. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Mechanic extraction — that is P4's responsibility |
| :---- |
| ✗  visual\_type assignment — removed from P3b entirely |
| ✗  search\_query generation — removed from P3b entirely |
| ✗  LLM calls of any kind |
| ✗  Display logic or terminal print statements beyond stage status |

*⚠ SoC violation: current P3b calls mechanic\_extractor and sets visual\_type. These must be removed and moved to P4.*

**P4 — Mechanic Extraction \[NEEDS REFACTOR\]**  
*Runner: stage\_p4\_extract.py (rename from stage\_p4\_assets.py)*

| Inputs | asset\_briefs rows written by P3b (segment\_text per row) |
| :---- | :---- |
| **Outputs** | asset\_briefs rows updated with: game\_title, mechanic, moment, search\_queries (JSON array). visual\_type NOT set here. |
| **Core Modules Called** | mechanic\_extractor.py \+ llm\_client.py (DeepSeek) |
| **Success Condition** | On LLM failure for a segment: write mechanic=unknown, game\_title=null, moment=unknown. Continue to next segment. Never halt full stage. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Asset sourcing or downloading |
| :---- |
| ✗  Prompt building or drawtext construction |
| ✗  visual\_type assignment — that belongs to P4b |
| ✗  DB writes beyond asset\_briefs mechanic columns |

*⚠ SoC violation: mechanic extraction is currently embedded inside stage\_p3b\_segment.py. Must be extracted to its own stage.*

**P4b — Asset Sourcing \[NEEDS REFACTOR\]**  
*Runner: stage\_p4b\_source.py*

| Inputs | asset\_briefs rows with game\_title, mechanic, moment populated by P4 |
| :---- | :---- |
| **Outputs** | asset\_briefs rows updated with: selected\_asset (file path), asset\_source, status=sourced. visual\_type set here based on what was actually found. |
| **Core Modules Called** | asset\_sourcer.py \+ index\_manager.py \+ prompt\_builder.py (new) |
| **Success Condition** | Priority chain: local library → YouTube (if enabled) → Wikimedia → Pollinations. Pollinations is the guaranteed fallback — it must never fail silently. If Pollinations fails twice: write solid colour frame path. |
| **Failure / Fallback** |  |

Sourcing priority when youtube\_clip\_enabled=false (MVP mode):

* 1\. Local gameplay library (assets/gameplay/)

* 2\. Pollinations.ai AI image generation

* 3\. Solid colour fallback frame (\#1a1a2e dark blue)

Forbidden dependencies:

| ✗  Prompt construction — call prompt\_builder.py, do not build prompts inline |
| :---- |
| ✗  drawtext string construction — that is prompt\_builder.py responsibility |
| ✗  Display logic or terminal print statements beyond sourcing status |
| ✗  FFmpeg calls of any kind |
| ✗  Mechanic extraction logic |

*⚠ SoC violation: asset\_sourcer.py currently contains prompt building, drawtext construction, and key phrase extraction. All three move to prompt\_builder.py.*

**P4c — YouTube Clip Sourcing \[DISABLED \- MVP\]**  
*Runner: called by asset\_sourcer.py when youtube\_clip\_enabled=true*

| Inputs | search\_queries\[\] from asset\_briefs \+ segment\_text \+ keywords |
| :---- | :---- |
| **Outputs** | Downloaded clip file in assets/clips/ OR None if threshold not met |
| **Core Modules Called** | youtube\_sourcer.py \+ index\_manager.py \+ llm\_client.py (DeepSeek judge) |
| **Success Condition** | Confidence \<0.8 on all 5 candidates: return None. Caller (P4b) handles fallback to Pollinations. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Pollinations calls — fallback is P4b's responsibility |
| :---- |
| ✗  DB writes beyond index\_manager calls |
| ✗  Prompt building or drawtext construction |
| ✗  FFmpeg calls |

*NOTE: youtube\_sourcer.py is built and functional. yt-dlp requires node runtime \+ \--remote-components ejs:github flag. Disabled in MVP via config.yaml: youtube\_clip\_enabled: false.*

**P5 — Prompt Building \[PLANNED\]**  
*Runner: stage\_p5\_prompts.py (not yet created)*

| Inputs | asset\_briefs rows with game\_title, mechanic, moment, segment\_text, selected\_asset, asset\_source |
| :---- | :---- |
| **Outputs** | asset\_briefs rows updated with: pollinations\_prompt (if ai\_generated), drawtext\_string, key\_phrase |
| **Core Modules Called** | prompt\_builder.py (new — extracted from asset\_sourcer.py and assembler.py) |
| **Success Condition** | On empty segment\_text: write empty string to key\_phrase and drawtext\_string. Never halt. |
| **Failure / Fallback** |  |

prompt\_builder.py contract (pure functions, no external dependencies):

* build\_pollinations\_prompt(game\_title, mechanic, moment) → str

* build\_drawtext\_string(key\_phrase) → str

* extract\_key\_phrase(segment\_text, max\_words=9) → str

* build\_infographic\_prompt(segment\_text) → str (for ai\_image type segments)

Forbidden dependencies:

| ✗  DB reads or writes — all inputs passed as parameters |
| :---- |
| ✗  API calls of any kind |
| ✗  Config reads |
| ✗  File I/O |
| ✗  LLM calls — prompt\_builder.py is pure Python string construction only |

*NOTE: prompt\_builder.py must be fully testable with zero mocking. Every function takes primitives, returns strings.*

**P6 — Voice Synthesis \[BUILT\]**  
*Runner: stage\_p6\_audio.py*

| Inputs | Approved scripts table row (hook\_short\_script \+ mid\_form\_body) |
| :---- | :---- |
| **Outputs** | audio/hook.mp3 \+ audio/body.mp3 written to disk |
| **Core Modules Called** | edge-tts Python library |
| **Success Condition** | On TTS failure: retry once. On second failure: halt stage, report error. Do not assemble video without audio. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  Asset sourcing or prompt building |
| :---- |
| ✗  FFmpeg calls |
| ✗  DB writes beyond updating script status |
| ✗  LLM calls |

Current violations: None. P6 is clean.

*NOTE: Voice: en-US-GuyNeural (MVP). Rate: \-5% for analytical pacing. Voice identity flagged as OQ-007 — Kokoro TTS evaluation deferred post-MVP.*

**P7 — Video Assembly \[NEEDS REFACTOR\]**  
*Runner: stage\_p7\_assemble.py*

| Inputs | Ordered asset\_briefs rows with selected\_asset \+ drawtext\_string \+ estimated\_duration\_s. Audio files from P6. |
| :---- | :---- |
| **Outputs** | output/video\_N.mp4 written to disk |
| **Core Modules Called** | assembler.py \+ FFmpeg (subprocess) |
| **Success Condition** | On FFmpeg failure: log full stderr, write status=failed to render\_jobs, halt. Never produce a partial video silently. |
| **Failure / Fallback** |  |

FFmpeg behaviour:

* Stills: Ken Burns pan/zoom via zoompan filter. Direction seeded per asset for reproducibility.

* Clips: Direct play, trimmed to estimated\_duration\_s

* Drawtext: Applied per segment from drawtext\_string field in asset\_briefs

* Subtitles: Whisper transcription if subtitles\_enabled=true in config. SRT and/or burn per subtitle\_mode.

* Output: 1920×1080 mid-form, 1080×1920 Short. Config-driven.

Forbidden dependencies:

| ✗  Key phrase extraction — must receive pre-built drawtext\_string from asset\_briefs |
| :---- |
| ✗  Prompt building of any kind |
| ✗  DB reads beyond render\_jobs and asset\_briefs |
| ✗  LLM calls |
| ✗  Asset sourcing or downloading |

*⚠ SoC violation: assembler.py currently contains \_extract\_key\_phrase(). This moves to prompt\_builder.py. Assembler receives drawtext\_string as a field, never constructs it.*

**P8 — Package Output \[PLANNED\]**  
*Runner: stage\_p8\_package.py (not yet created)*

| Inputs | Completed render\_jobs row \+ scripts table row \+ asset\_briefs rows |
| :---- | :---- |
| **Outputs** | output/package\_N/ directory containing: video MP4, thumbnail, metadata.json, description.txt, tags.txt |
| **Core Modules Called** | TBD — Python file I/O \+ Jinja2 or f-string templating |
| **Success Condition** | On missing video file: halt. On missing metadata fields: write placeholder strings, continue, flag in report. |
| **Failure / Fallback** |  |

metadata.json schema:

* title: from scripts.title\_suggestion

* description: generated from script summary \+ source credits

* tags: from scripts.tags JSON array

* category: Gaming (YouTube category ID 20\)

* privacy: unlisted (default until director sets public)

Forbidden dependencies:

| ✗  LLM calls |
| :---- |
| ✗  FFmpeg calls |
| ✗  Asset sourcing |
| ✗  YouTube API calls — those belong to P9 |

**P9 — Publishing \[FUTURE\]**  
*Runner: stage\_p9\_publish.py (not yet created)*

| Inputs | output/package\_N/ directory from P8 |
| :---- | :---- |
| **Outputs** | Published YouTube video URL written to render\_jobs.published\_url |
| **Core Modules Called** | YouTube Data API v3 (OAuth2) |
| **Success Condition** | On API failure: log error, write status=publish\_failed, halt. Never retry publishing automatically — director must re-authorise. |
| **Failure / Fallback** |  |

Forbidden dependencies:

| ✗  LLM calls |
| :---- |
| ✗  FFmpeg calls |
| ✗  Asset sourcing |
| ✗  Script generation |

*NOTE: OQ-009: YouTube Data API v3 OAuth2 setup requires Google Cloud project and consent screen. Director must complete this manually. Pipeline cannot automate account creation.*

# **6\. SoC/SRP Violation Inventory**

All known violations as of v0.5. Each must be resolved before the affected stage is considered production-ready.

| V-001 — ACTIVE | asset\_sourcer.py contains prompt building, drawtext construction, and key phrase extraction. Target: extract all three to prompt\_builder.py. |
| :---- | :---- |
| **V-002 — ACTIVE** | assembler.py contains \_extract\_key\_phrase(). Target: remove, call prompt\_builder.py instead. |
| **V-003 — ACTIVE** | stage\_p3b\_segment.py calls mechanic\_extractor and sets visual\_type. Target: remove both. Mechanic extraction moves to P4. visual\_type removed from P3b entirely. |
| **V-004 — ACTIVE** | stage runners contain display/print logic mixed with orchestration. Target: all display moves to a Logger class. Stage runners call logger.stage\_complete() etc. |
| **V-005 — ACTIVE** | asset\_sourcer.py reads config at module level via global. Target: config passed as parameter from stage runner. |

# **7\. Module Contracts (Section 11\)**

Each core module has exactly one responsibility. Forbidden dependencies are enforced via code review and test isolation. A module that requires mocking more than one external dependency in tests is a sign of SRP violation.

| core/db.py | Responsibility: DB connection, schema init, WAL. Forbidden: business logic, LLM calls, file I/O outside database/. |
| :---- | :---- |
| **core/segmentation.py** | Responsibility: Split script into paragraph segments. Write segment rows. Forbidden: mechanic extraction, asset sourcing, LLM calls, display logic, visual\_type assignment. |
| **core/mechanic\_extractor.py** | Responsibility: Extract game/mechanic/moment from segment text via LLM. Forbidden: DB writes, asset sourcing, display logic, config reads. |
| **core/prompt\_builder.py (new)** | Responsibility: Build Pollinations prompts, drawtext strings, key phrases. Pure functions only. Forbidden: DB reads, API calls, config reads, file I/O, LLM calls. |
| **core/asset\_sourcer.py** | Responsibility: Select and retrieve one asset per segment. Call prompt\_builder for prompts. Forbidden: prompt construction inline, drawtext construction, display logic, FFmpeg calls. |
| **core/youtube\_sourcer.py** | Responsibility: YouTube search, transcript fetch, LLM relevance judgment, clip download. Forbidden: DB writes beyond index\_manager calls, Pollinations calls, FFmpeg calls. |
| **core/assembler.py** | Responsibility: FFmpeg orchestration only. Receive pre-built inputs. Forbidden: key phrase extraction, prompt building, DB reads beyond asset\_briefs/render\_jobs, LLM calls. |
| **core/index\_manager.py** | Responsibility: Read/write game\_clip\_index table. Record attempts and successes. Forbidden: YouTube calls, LLM calls beyond expand\_index(). |
| **core/llm\_client.py** | Responsibility: OpenRouter HTTP client. Send prompts, return text. Forbidden: JSON parsing, business logic, DB reads, config reads beyond API key. |
| **stage\_p\*.py (all runners)** | Responsibility: Orchestrate one stage. Load from DB, call core modules, write to DB. Forbidden: business logic, LLM calls, FFmpeg calls, prompt construction, display logic beyond status lines. |
| **pipeline\_run.py** | Responsibility: Call stage runners in sequence. Report completion. Forbidden: everything except stage runner calls and top-level status reporting. |

# **8\. Refactor Priority Order**

Address violations in this order. Each violation resolved and tested before next begins.

| Priority 1 | Create core/prompt\_builder.py. Extract build\_pollinations\_prompt, build\_drawtext\_string, extract\_key\_phrase from asset\_sourcer.py and assembler.py. Write tests. Resolves V-001 and V-002. |
| :---- | :---- |
| **Priority 2** | Remove mechanic extraction and visual\_type from stage\_p3b\_segment.py. Create stage\_p4\_extract.py as dedicated mechanic extraction stage. Resolves V-003. |
| **Priority 3** | Create stage\_p5\_prompts.py. Wire prompt\_builder.py as a pipeline stage between P4b and P6. Resolves remaining prompt-building residue. |
| **Priority 4** | Extract display logic from all stage runners into a Logger class. Resolves V-004. |
| **Priority 5** | Pass config as parameter rather than module-level global in asset\_sourcer.py. Resolves V-005. |

# **9\. Data Model**

| topics | Topic queue. input\_mode, status, angle, notes. |
| :---- | :---- |
| **sources** | Research sources. source\_type, url, summary, used\_in\_script. |
| **scripts** | Generated scripts. hook\_short\_script, mid\_form\_body, word counts, title\_suggestion, tags, approved. |
| **asset\_briefs** | Per-segment asset metadata. segment\_text, estimated\_duration\_s, game\_title, mechanic, moment, visual\_type, selected\_asset, drawtext\_string, key\_phrase, pollinations\_prompt. |
| **render\_jobs** | Assembly jobs. format, subtitles\_enabled, subtitle\_mode, output\_path, status, published\_url. |
| **game\_clip\_index** | YouTube clip knowledge base. game\_title, mechanic, search\_query, confidence\_avg, times\_successful, verified. |

# **10\. Architectural Decision Records**

| ADR-001 | Manual Brief Mode. Phase 1 validation via handcrafted JSON brief bypassing P1/P2. Permanent supported input mode. |
| :---- | :---- |
| **ADR-002** | Dual-Format Script JSON Contract. hook\_short\_script and mid\_form\_body as separate fields. Concatenation programmatic. |
| **ADR-003** | SQLite WAL. PRAGMA journal\_mode=WAL unconditional at DB init. |
| **ADR-004** | Unified OpenRouter LLM Client. All LLM calls via single OpenRouter client ported from OpenAgent. Direct Anthropic SDK deferred. |
| **ADR-005** | Transcript-First Visual Assembly. Paragraph boundaries define segment cuts. P4 and P6 run in parallel. Whisper for subtitles only. |
| **ADR-006** | YouTube Clip Sourcing. yt-dlp \+ DeepSeek relevance judge. 5 candidates, 0.8 threshold. Pollinations fallback. Disabled in MVP. |
| **ADR-007 — NEW** | SoC/SRP Enforcement. No module may contain logic belonging to another module's contract. Violations V-001 through V-005 must be resolved before any new pipeline features are added. prompt\_builder.py is a pure module with zero external dependencies. |

# **11\. Open Questions**

| OQ-001 — ACTIVE | P2 web search API: Brave Search vs alternatives. Resolve before P2 implementation. |
| :---- | :---- |
| **OQ-003** | Channel identity: separate from rfditservices.com or linked? |
| **OQ-004** | Content cadence target: affects queue depth planning. |
| **OQ-005** | GDC Vault free tier access. Confirm before P2. |
| **OQ-006** | AI image quality: Pollinations.ai acceptable for MVP fallback stills? |
| **OQ-007** | Voice identity: GuyNeural flagged as generic. Kokoro TTS evaluation deferred post-MVP. |
| **OQ-008** | yt-dlp YouTube rate limiting at volume. YouTube Data API v3 as fallback search. |
| **OQ-009** | YouTube Data API v3 OAuth2 setup for P9 publishing. Director must complete manually. |
| **OQ-010 — NEW** | Short format assembly: hook segment only or hook \+ one body segment? Affects P7 short render logic. |

# **12\. Next Steps**

* Resolve V-001/V-002: Create core/prompt\_builder.py and update asset\_sourcer.py and assembler.py

* Resolve V-003: Extract mechanic extraction from stage\_p3b\_segment.py into stage\_p4\_extract.py

* Run full pipeline\_run.py after refactor — first clean end-to-end run

* Evaluate Pollinations output quality on first complete video

* Resolve OQ-003 — channel identity decision before publishing

* Resolve OQ-007 — voice identity before first public video

*ContentEngine SDD v0.5  —  RFD IT Services Ltd.  —  April 2026  —  Definitive Edition*
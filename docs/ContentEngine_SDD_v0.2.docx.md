**ContentEngine**

Software Design Document v0.2

*AI-Powered YouTube Content Pipeline*

April 2026  —  RFD IT Services Ltd.

*Revised: ADR-001 Manual Brief Mode • ADR-002 Dual-Format Contract • ADR-003 SQLite WAL*

# **Revision History**

| v0.1 — April 2026 | Initial SDD. 7-phase pipeline, dual-format output, SQLite storage, OpenRouter LLM routing. |
| :---- | :---- |
| **v0.2 — April 2026** | ADR-001: Manual Brief Mode adopted as Phase 1 validation strategy. ADR-002: Dual-format script separated into strict JSON contract (hook\_short\_script / mid\_form\_body). ADR-003: SQLite WAL unconditionally enabled. Asset briefs default to screen recording directives, not AI image prompts. Phase map reordered to reflect reversed pipeline. |

# **1\. Purpose & Scope**

ContentEngine is a standalone Python pipeline for generating, researching, and packaging short-form YouTube content. It operates as an AI-assisted production system with a human director at the top of the execution model.

The primary output is dual-format video content: mid-form explainers (3–5 minutes) and repurposed Shorts (\<60 seconds), both built from the same research brief and script. The initial content domain is game mechanics and game design analysis.

This system is architecturally separate from OpenAgent and rpgCore but follows the same Spec-Driven Development discipline: phase gates, test anchors, and AGENT\_CONTRACT.md before implementation.

# **2\. System Architecture**

## **2.1 Execution Model**

ContentEngine follows the established three-layer model:

* Director (Robert) — picks topic, sets angle, approves script, approves final output

* Pipeline (ContentEngine) — research, script generation, asset briefs, packaging

* Coding Agent (Antigravity) — implements pipeline stages per directive

Director input depth is variable. Three modes are permanently supported:

| Topic Only | Director provides a subject. Pipeline infers angle, generates research brief, drafts script autonomously. |
| :---- | :---- |
| **Topic \+ Angle** | Director provides subject and a specific lens or question. Pipeline researches and scripts to that angle. |
| **Topic \+ Notes** | Director provides subject, angle, and rough bullet points. Pipeline polishes into a full script. |

| Manual Brief Mode | Director provides a fully handcrafted JSON brief, bypassing P1/P2 entirely. Permanent feature. Primary mode for Phase 1 validation and bespoke deep-dive content. See ADR-001. |
| :---- | :---- |

## **2.2 Pipeline Stages**

Each stage is an independent Python module. Stages are stateful — outputs persist to SQLite and can be resumed or rerun. Manual Brief Mode enters at P3, bypassing P1 and P2.

| Phase | Name | Responsibility | Output |
| :---- | :---- | :---- | :---- |
| P1 | Brief Generation | AI (DeepSeek via OpenRouter) | topic\_briefs row — BYPASSED in Manual Mode |
| P2 | Research Execution | AI \+ Web Sources | sources rows — BYPASSED in Manual Mode |
| P3 | Script Drafting | Claude Sonnet via API | JSON: hook\_short\_script \+ mid\_form\_body (see ADR-002) |
| P4 | Short Extraction | Programmatic — no LLM | Renders hook\_short\_script field as standalone Short |
| P5 | Asset Brief | AI | Screen recording directives keyed to script segments |
| P6 | Voice Synthesis | ElevenLabs API | audio/ artifact per format |
| P7 | Package Output | Python | Output manifest JSON \+ folder structure |

## **2.3 Dual-Format Script Contract (ADR-002)**

Scripts are generated as a structured JSON object. The hook and body are strictly separated fields. The LLM prompt contract forbids the mid\_form\_body from referencing the hook to maintain full Short independence.

| hook\_short\_script | Self-contained, 45–55 second segment. No dependencies on body content. Rendered alone for Shorts. Prepended to body for mid-form. |
| :---- | :---- |
| **mid\_form\_body** | Remaining 2.5–4 minutes of content. Must not reference hook by implication. Standalone readable from the hook alone. |
| **Concatenation rule** | mid\_form \= hook\_short\_script \+ mid\_form\_body. This is programmatic, not LLM-generated. |
| **Short render flag** | format=short renders hook\_short\_script only. format=mid\_form renders concatenated output. |

*NOTE: The LLM is never asked to produce a single monolithic script. The JSON contract is enforced at the prompt level and validated by test anchors before any audio is generated.*

## **2.4 Asset Brief Strategy**

Asset briefs default to screen recording directives rather than AI image generation prompts. AI-generated visuals for specific game UI elements and mechanics are unreliable at MVP scale. Screen recordings are more credible for a game mechanics channel and require no generation pipeline.

| Default brief type | Screen recording directive with timestamp, game title, and mechanic target |
| :---- | :---- |
| **Example** | "Record 10s of Balatro showing a hand evaluation — close-up on scoring multiplier stack" |
| **AI image prompts** | Reserved for abstract concept illustrations only — not game-specific UI |
| **Upgrade path** | AI image generation added in Phase 5+ once recording workflow is validated |

# **3\. Data Model**

## **3.1 Storage**

All persistent state lives in content\_engine.db (SQLite). WAL mode is unconditionally enabled at initialization per ADR-003. Schema versioned via SCHEMA\_VERSION constant.

| PRAGMA journal\_mode=WAL | Enabled unconditionally at DB init. Allows concurrent readers and writers during background LLM/TTS tasks. |
| :---- | :---- |
| **SCHEMA\_VERSION** | Integer constant. Increment on any schema change. Checked at startup. |
| **Location** | database/content\_engine.db — gitignored. Schema in database/schema.sql — version controlled. |

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

### **sources**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| topic\_id | INTEGER FK | References topics.id |
| source\_type | TEXT | gdc | wiki | interview | blog | paper | reddit | creator | other |
| title | TEXT | Source title |
| url | TEXT NULL | URL if applicable |
| summary | TEXT | AI-generated summary of relevant content |
| used\_in\_script | INTEGER | Boolean — 1 if cited in final script |
| retrieved\_at | TEXT | ISO 8601 |

### **scripts**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| topic\_id | INTEGER FK | References topics.id |
| version | INTEGER | Increments on regeneration |
| hook\_short\_script | TEXT | Self-contained Short segment. 45–55s. See ADR-002. |
| mid\_form\_body | TEXT | Body content only. Concatenated with hook for mid-form render. |
| word\_count\_hook | INTEGER | Word count of hook segment |
| word\_count\_body | INTEGER | Word count of body segment |
| estimated\_duration\_s | INTEGER | Total mid-form estimated duration in seconds |
| approved | INTEGER | Boolean — director approval flag |
| created\_at | TEXT | ISO 8601 |

### **asset\_briefs**

| Field | Type | Description |
| :---- | :---- | :---- |
| id | INTEGER PK | Auto-increment |
| script\_id | INTEGER FK | References scripts.id |
| segment\_index | INTEGER | Script segment index this brief covers |
| brief\_type | TEXT | screen\_recording | ai\_image | stock\_footage |
| directive | TEXT | Screen recording instruction or image prompt |
| game\_title | TEXT NULL | Target game for screen recording briefs |
| duration\_s | INTEGER NULL | Target recording length in seconds |
| status | TEXT | pending | sourced | approved |

# **4\. Research Source Registry**

Source categories in priority order for credibility and citability. Active in P1/P2 automated modes. Included manually in Manual Brief Mode JSON.

| GDC / Postmortems | GDC Vault, GDC YouTube — free tier access confirmed required before relying on Vault content (OQ-005) |
| :---- | :---- |
| **Academic Papers** | Google Scholar, DiGRA proceedings, IEEE Xplore |
| **Developer Interviews** | Blogs, podcasts, developer posts, studio dev diaries |
| **Game Wikis** | Fandom, official wikis — mechanic descriptions and patch history |
| **Community Discussion** | Reddit (r/gamedesign, r/indiegaming), Discord archives |
| **Content Creators** | Cited by name and video only — not scraped |
| **Patch Notes** | Official patch notes for mechanic evolution tracking |

# **5\. External Tooling**

| Script Generation (P3) | Claude Sonnet via Anthropic API direct |
| :---- | :---- |
| **Research / Brief (P1)** | DeepSeek V3 via OpenRouter — deferred to Phase 2+ |
| **Web Research (P2)** | TBD — Brave Search API preferred. See OQ-001. |
| **Voice Synthesis (P6)** | ElevenLabs API — synthetic voice. Clone deferred. |
| **Visual Assets** | Screen recordings (primary). Midjourney/Flux for abstract stills only. |
| **Video Assembly** | CapCut or DaVinci — manual at MVP, outside pipeline scope |
| **Storage** | SQLite — WAL enabled. Python sqlite3 stdlib. |
| **Config** | YAML config file — consistent with OpenAgent pattern |

# **6\. Development Phase Map**

Phase map revised to reflect Manual Brief Mode as the Phase 1 validation entry point. Automated research (P1/P2) moves to Phase 2 after script-to-audio output is validated.

| Phase | Name | Responsibility | Output |
| :---- | :---- | :---- | :---- |
| Phase 1 | Reverse Pipeline Validation | Manual Brief → P3 Script → P6 Audio. SQLite schema \+ WAL. AGENT\_CONTRACT.md. 10 test anchors. | Validated audio output from a handcrafted brief |
| Phase 2 | Automated Research Layer | P1 Brief Generation \+ P2 Research Execution \+ web search API integration | Working research output feeding P3 |
| Phase 3 | Asset Brief System | P5 screen recording directives keyed to script segments | Per-segment directives ready for recording |
| Phase 4 | Packaging | P7 output manifest \+ folder structure \+ metadata export | Publishable asset package per video |
| Phase 5 | CLI & Queue Management | Topic queue, batch runs, full CLI interface | End-to-end pipeline from topic to package |
| Phase 6 | Automation & Scheduling | Scheduled runs, output monitoring, cadence tracking | Autonomous pipeline with director review gates |

*NOTE: Phase 1 begins after AGENT\_CONTRACT.md is authored and 10 test anchors are defined. No implementation precedes the contract. This is non-negotiable.*

# **7\. CLI Interface (Target)**

| content-engine add | Add topic to queue (interactive — prompts for mode, angle, notes) |
| :---- | :---- |
| **content-engine brief \<file\>** | Load a Manual Brief JSON file into the database, bypassing P1/P2 |
| **content-engine script \<id\>** | Run P3 script generation for a topic |
| **content-engine review \<id\>** | Print hook \+ body \+ asset briefs for director approval |
| **content-engine approve \<id\>** | Mark script approved, advance to voice synthesis |
| **content-engine audio \<id\>** | Run P6 ElevenLabs voice synthesis for approved script |
| **content-engine package \<id\>** | Generate output manifest and folder structure |
| **content-engine status** | Show queue status across all topics |
| **content-engine sources \<id\>** | List all sources with citation flags |

# **8\. Design Constraints & Decisions**

* Standalone repo — not extended from OpenAgent. Shares philosophy, not codebase.

* SQLite \+ WAL — no external database at MVP. WAL unconditional per ADR-003.

* Manual Brief Mode is a permanent feature — not a workaround. Bypasses P1/P2 by design per ADR-001.

* Dual-format via JSON contract — hook and body are separate fields, never a monolithic script per ADR-002.

* Short is rendered from hook\_short\_script field only — concatenation is programmatic, not LLM-generated.

* Asset briefs default to screen recording directives — AI image generation deferred.

* Source attribution is non-optional — every automated script must be citeable.

* Voice clone deferred — ElevenLabs synthetic voice for MVP, switchable with no pipeline changes.

* Video assembly is manual at MVP — CapCut/DaVinci outside pipeline scope until Phase 5+.

* OpenRouter for research LLM — same two-stage routing pattern as OpenAgent.

# **9\. Architectural Decision Records**

*NOTE: ADRs are also maintained as standalone files in docs/adr/ within the repository.*

## **ADR-001: Pipeline Validation via Manual Brief Mode**

| ADR-001 | Pipeline Validation via Manual Brief Mode |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | Building automated web-scraping and research synthesis (P1/P2) before validating the quality of the final audio/video output (P3–P6) introduces high risk of wasted engineering effort. Automated research is complex and expensive to debug. The end-product quality is unknown. |
| **Decision** | Phase 1 exclusively implements Manual Brief Mode. The system accepts a handcrafted structured JSON brief and passes it directly to P3 (Scripting) and P6 (Audio). Automated research (P1/P2) is deferred to Phase 2 after output quality is validated. |
| **Consequences** | Defers engineering cost of web scraping and RAG infrastructure. Guarantees the script-to-audio pipeline is proven before building the research layer. Establishes Manual Brief Mode as a permanent, supported input mode for bespoke content. Mirrors the rpgCore-first validation strategy used across other projects. |
| **Rejected alternatives** | PostgreSQL \+ pgvector RAG pipeline: intellectually satisfying but violates KISS for MVP. Massive infrastructure detour before output quality is known. Headlong automated build: high risk of debugging research scraping before knowing if the output is worth producing. |

## **ADR-002: Dual-Format Script JSON Contract**

| ADR-002 | Dual-Format Script JSON Contract |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | Relying on the first 45 seconds of a monolithic mid-form script to double as a standalone Short creates narrative fragility. If the mid-form body references or depends on the hook, the Short breaks as an independent unit. Editing lock-in increases. |
| **Decision** | The P3 LLM scripting prompt enforces a structured JSON output with two fields: hook\_short\_script (45–55s, self-contained, Short-ready) and mid\_form\_body (remaining content, no hook dependencies). The LLM is explicitly forbidden from referencing the hook within the body. Concatenation for mid-form is programmatic. |
| **Consequences** | Shorts can be rendered and published independently at any time. Mid-form is assembled deterministically. Test anchors validate JSON structure before any audio is generated. Script versioning tracks both fields independently. |
| **Rejected alternatives** | Monolithic script with AI-selected Short clip: AI clip selection is unreliable and creates post-production dependency. Manual Short selection: viable fallback but not scalable as a primary method. |

## **ADR-003: SQLite WAL Configuration**

| ADR-003 | SQLite WAL Configuration |
| :---- | :---- |
| **Status** | Accepted — April 2026 |
| **Context** | The pipeline runs long background tasks (LLM generation, ElevenLabs TTS) while the director queries job status via CLI. Standard SQLite journal mode locks the database during write operations, causing lockouts during generation runs. |
| **Decision** | PRAGMA journal\_mode=WAL; is executed unconditionally in the database initialization function. No configuration flag. No override. Always on. |
| **Consequences** | Simultaneous readers and writers permitted without lockouts. Minimal performance overhead. Write-ahead log improves data integrity on interrupted writes. Standard sqlite3 stdlib — no additional dependencies. |
| **Rejected alternatives** | PostgreSQL: unnecessary server infrastructure for a local single-user pipeline. Deferred WAL: adding it later risks subtle concurrency bugs in already-deployed code. |

# **10\. Open Questions**

| OQ-001 — ACTIVE | Web search API for P2: Brave Search (generous free tier) vs SerpAPI vs direct scraping. Must resolve before Phase 2 begins. Brave Search preferred pending cost review. |
| :---- | :---- |
| **OQ-002 — RESOLVED** | Dual-format script separation. Resolved by ADR-002: JSON contract with hook\_short\_script and mid\_form\_body fields. |
| **OQ-003** | Channel name and identity: separate from rfditservices.com brand or linked? Affects title cards and asset style. |
| **OQ-004** | Content cadence target: one video per week? Two? Affects queue depth and pipeline throughput planning. |
| **OQ-005** | GDC Vault free tier access limitations. Confirm source availability before Phase 2 research layer depends on it. |

# **11\. Next Steps**

* Create repo: content-engine (visibility TBD)

* Author AGENT\_CONTRACT.md — rules of engagement, phase gating, test anchor requirements

* Define 10 Phase 1 test anchors in tests/test\_p1\_anchors.py — covering DB WAL confirmation, JSON script structure, hook word count bounds, manual brief loading

* Resolve OQ-001 — Brave Search API vs alternatives before Phase 2 scoping

* Select first Manual Brief topic — candidate: Balatro deck-building math or inventory tension in Dave the Diver

* Issue Phase 1 directive to Antigravity

*ContentEngine SDD v0.2  —  RFD IT Services Ltd.  —  April 2026*
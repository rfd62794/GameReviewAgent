# AGENT_CONTRACT.md — ContentEngine

**Version:** 1.0  
**SDD Reference:** ContentEngine_SDD_v0.2  
**Date:** April 2026

---

## 1. Purpose

This contract defines the rules of engagement between the Director (Robert) and the Coding Agent (Antigravity) for all ContentEngine development. It codifies phase gating, test anchor requirements, and approval workflows.

No code is committed, no phase is advanced, and no external API is called without satisfying the conditions in this contract.

---

## 2. Phase Gating Rules

### 2.1 No Phase Advances Without Prior Phase Tests Passing

**RULE:** A phase is not considered complete until ALL test anchors for that phase pass with zero failures.

- `pytest tests/test_p1_anchors.py` must report **0 failures** before any Phase 2 work begins.
- Each subsequent phase will have its own `test_p{N}_anchors.py` file.
- A failing test anchor is a **hard stop**. No workarounds. No "we'll fix it later."

### 2.2 Phase Gate Checklist

| Phase | Gate Condition | Approver |
|-------|---------------|----------|
| Phase 1 | All 10 P1 test anchors pass. Director reviews schema.sql, manual_brief.py, script_generation.md, AGENT_CONTRACT.md. | Director |
| Phase 2 | P1 gate satisfied. P2 test anchors pass. Research pipeline produces valid sources. | Director |
| Phase 3 | P2 gate satisfied. P3 test anchors pass. Asset briefs generated for at least one script. | Director |
| Phase 4 | P3 gate satisfied. P4 test anchors pass. Output manifest generated. | Director |
| Phase 5 | P4 gate satisfied. CLI functional. End-to-end pipeline validated. | Director |
| Phase 6 | P5 gate satisfied. Scheduling and monitoring validated. | Director |

### 2.3 Director Approval Is Non-Negotiable

The Agent does not:
- Advance to the next phase without explicit Director approval
- Call external APIs (Anthropic, ElevenLabs, OpenRouter) without Director go-ahead
- Merge or deploy without Director review
- Skip or defer test anchor failures

The Agent may:
- Propose phase advancement after demonstrating all gate conditions
- Suggest test additions beyond the minimum anchor count
- Refactor within a phase without re-approval (provided tests still pass)

---

## 3. Test Anchor Requirements

### 3.1 Minimum Anchor Count

Each phase requires a **minimum of 10 test anchors** defined before implementation begins.

### 3.2 Phase 1 Test Anchors (tests/test_p1_anchors.py)

| # | Anchor | Description |
|---|--------|-------------|
| 1 | WAL Mode Confirmation | `PRAGMA journal_mode` returns `wal` after DB init |
| 2 | Schema Version Check | `SCHEMA_VERSION` is a positive integer, retrievable |
| 3 | Schema Table Existence | All 4 core tables (topics, sources, scripts, asset_briefs) exist |
| 4 | Manual Brief Loading | JSON brief creates topic row with `input_mode='manual_brief'` |
| 5 | Manual Brief Validation | Invalid briefs rejected before DB insertion |
| 6 | JSON Script Structure | Valid script JSON passes contract validation |
| 7 | Hook Word Count — Lower | Hook < 90 words rejected |
| 8 | Hook Word Count — Upper | Hook > 120 words rejected |
| 9 | Forbidden Body Phrases | All 7 forbidden phrases detected in mid_form_body |
| 10 | Tags & Title Validation | Tag count bounds [5,10] and title length ≤ 80 enforced |

### 3.3 Test Anchor Design Principles

- **Anchors test contracts, not implementations.** A refactored module must still pass its anchors.
- **Anchors are additive.** New anchors can be added; existing anchors are never removed without Director approval.
- **Anchors run offline.** No test anchor may call an external API. Mock or fixture only.
- **Anchors are deterministic.** No randomness, no time-dependent assertions, no network calls.

---

## 4. Code Quality Standards

### 4.1 Module Independence

Each pipeline stage (P1–P7) is an independent Python module. Modules communicate through the SQLite database, not through direct imports of each other's internals.

### 4.2 Error Handling

- All external API calls wrapped in try/except with specific error types
- Database operations use transactions with explicit rollback on failure
- User-facing errors include actionable context (what failed, what to check)

### 4.3 Configuration

- API keys via environment variables (never hardcoded, never committed)
- File paths resolved relative to project root
- YAML config file for non-secret settings (deferred to Phase 5)

---

## 5. Deliverable Format

When the Agent completes a phase, it presents the following to the Director:

1. **File listing** — all new/modified files with one-line descriptions
2. **Test results** — full pytest output showing pass/fail status
3. **Open questions** — anything requiring Director decision before next phase
4. **Diff summary** — what changed since last review (after Phase 1)

The Director reviews, approves or requests changes, and explicitly authorizes the next phase.

---

## 6. ADR Compliance

All Architectural Decision Records in the SDD are binding:

- **ADR-001:** Manual Brief Mode is permanent. Never removed. Never degraded.
- **ADR-002:** Dual-format JSON contract. Hook and body are separate fields. LLM forbidden from referencing hook in body. Concatenation is programmatic.
- **ADR-003:** WAL mode unconditional. No configuration flag. No override. Always on.

Violations of ADR compliance are treated as test failures.

---

*AGENT_CONTRACT.md v1.0 — ContentEngine — RFD IT Services Ltd. — April 2026*

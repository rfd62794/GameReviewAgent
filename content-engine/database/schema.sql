-- ContentEngine Schema v1
-- SDD Reference: ContentEngine_SDD_v0.2, Section 3.2
-- ADR-003: WAL unconditionally enabled at database initialization.
PRAGMA journal_mode=WAL;

-- Schema version tracking. Increment on any schema change.
-- Checked at startup by core/db.py.
-- SCHEMA_VERSION = 1

CREATE TABLE IF NOT EXISTS topics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    domain          TEXT    NOT NULL CHECK (domain IN ('game_mechanics', 'game_design', 'indie_dev')),
    input_mode      TEXT    NOT NULL CHECK (input_mode IN ('topic_only', 'topic_angle', 'topic_notes', 'manual_brief')),
    angle           TEXT,
    notes           TEXT,
    status          TEXT    NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'researching', 'scripting', 'ready', 'published')),
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id        INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    source_type     TEXT    NOT NULL
                        CHECK (source_type IN ('gdc', 'wiki', 'interview', 'blog', 'paper', 'reddit', 'creator', 'other')),
    title           TEXT    NOT NULL,
    url             TEXT,
    summary         TEXT    NOT NULL,
    used_in_script  INTEGER NOT NULL DEFAULT 0,
    retrieved_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS scripts (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id                INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    version                 INTEGER NOT NULL DEFAULT 1,
    hook_short_script       TEXT    NOT NULL,
    mid_form_body           TEXT    NOT NULL,
    word_count_hook         INTEGER NOT NULL,
    word_count_body         INTEGER NOT NULL,
    estimated_duration_s    INTEGER NOT NULL,
    approved                INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS asset_briefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id       INTEGER NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    segment_index   INTEGER NOT NULL,
    brief_type      TEXT    NOT NULL CHECK (brief_type IN ('screen_recording', 'ai_image', 'stock_footage')),
    directive       TEXT    NOT NULL,
    game_title      TEXT,
    duration_s      INTEGER,
    status          TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sourced', 'approved'))
);

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_sources_topic      ON sources(topic_id);
CREATE INDEX IF NOT EXISTS idx_scripts_topic      ON scripts(topic_id);
CREATE INDEX IF NOT EXISTS idx_asset_briefs_script ON asset_briefs(script_id);

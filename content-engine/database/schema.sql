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
    title_suggestion        TEXT,
    tags                    TEXT,
    approved                INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS asset_briefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id       INTEGER NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    segment_index   INTEGER NOT NULL,
    segment_text    TEXT    NOT NULL,
    estimated_duration_s INTEGER NOT NULL,
    visual_type     TEXT    NOT NULL CHECK (visual_type IN ('gameplay_clip', 'stock_still', 'stock_clip', 'ai_image')),
    search_query    TEXT    NOT NULL,
    ai_image_prompt TEXT,
    selected_asset  TEXT,
    asset_source    TEXT    CHECK (asset_source IN ('pexels', 'wikimedia', 'local', 'ai_generated', NULL)),
    status          TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sourced', 'approved'))
);

CREATE TABLE IF NOT EXISTS render_jobs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id         INTEGER NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
    format            TEXT    NOT NULL CHECK (format IN ('mid_form', 'short')),
    subtitles_enabled INTEGER NOT NULL DEFAULT 0,
    subtitle_mode     TEXT    CHECK (subtitle_mode IN ('burn', 'srt', 'both', NULL)),
    output_path       TEXT,
    status            TEXT    NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'assembling', 'complete', 'failed')),
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at      TEXT
);

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_sources_topic      ON sources(topic_id);
CREATE INDEX IF NOT EXISTS idx_scripts_topic      ON scripts(topic_id);
CREATE INDEX IF NOT EXISTS idx_asset_briefs_script ON asset_briefs(script_id);
CREATE INDEX IF NOT EXISTS idx_render_jobs_script  ON render_jobs(script_id);

-- game_clip_index table
CREATE TABLE game_clip_index (
    id INTEGER PRIMARY KEY,
    game_title TEXT NOT NULL,
    mechanic TEXT NOT NULL,
    search_query TEXT NOT NULL,
    channel TEXT NULL,
    times_successful INTEGER DEFAULT 0,
    times_attempted INTEGER DEFAULT 0,
    confidence_avg REAL DEFAULT 0.0,
    verified INTEGER DEFAULT 0,
    suggested_by TEXT DEFAULT 'llm',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    last_used_at TEXT NULL
);

CREATE INDEX idx_game_mechanic 
ON game_clip_index(game_title, mechanic);

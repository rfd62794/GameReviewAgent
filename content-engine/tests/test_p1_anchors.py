"""
ContentEngine Phase 1 Test Anchors

SDD Reference: Section 6 (Phase 1), Section 11 (Next Steps)
Minimum 10 pytest stubs covering Phase 1 validation requirements:
  - WAL mode confirmation
  - JSON script structure validation
  - Hook word count bounds (90-120 words)
  - Manual brief loading
  - Schema version check

These tests MUST pass before any phase advancement.
See AGENT_CONTRACT.md for phase gating rules.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Ensure content-engine root is importable
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import init_db, get_connection, check_schema_version, SCHEMA_VERSION
from core.manual_brief import load_brief, validate_brief, ManualBriefError
from core.script_generator import (
    validate_script_json,
    HOOK_WORD_MIN,
    HOOK_WORD_MAX,
    BODY_WORD_MIN,
    BODY_WORD_MAX,
    FORBIDDEN_BODY_PHRASES,
)


# --- Fixtures ---


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database initialized with schema."""
    db_path = tmp_path / "test_content_engine.db"
    conn = init_db(db_path)
    conn.close()
    return db_path


@pytest.fixture
def sample_brief(tmp_path):
    """Create a sample manual brief JSON file."""
    brief = {
        "title": "Idle Clicker Prestige Loops — Why Resetting Everything Feels Like Winning",
        "domain": "game_mechanics",
        "angle": "The psychology and game design behind prestige mechanics in idle/clicker games",
        "notes": "Focus on why voluntary reset is compelling. Reference Cookie Clicker, Adventure Capitalist, Realm Grinder.",
        "sources": [
            {
                "source_type": "blog",
                "title": "The Math Behind Idle Games",
                "url": "https://blog.kongregate.com/the-math-of-idle-games-part-i/",
                "summary": "Kongregate analysis of exponential growth curves and prestige multiplier stacking in idle games.",
            },
            {
                "source_type": "gdc",
                "title": "Idle Games: The Mechanics and Monetization of Self-Playing Games",
                "url": "https://www.gdcvault.com/play/idle-games",
                "summary": "GDC talk on the core loop design of idle/clicker games, including prestige as a retention mechanic.",
            },
            {
                "source_type": "reddit",
                "title": "r/incremental_games — Why prestige systems work",
                "url": "https://www.reddit.com/r/incremental_games/",
                "summary": "Community discussion on the psychological satisfaction of prestige resets and permanent progression.",
            },
            {
                "source_type": "wiki",
                "title": "Cookie Clicker Wiki — Ascension Mechanics",
                "url": "https://cookieclicker.fandom.com/wiki/Ascension",
                "summary": "Detailed breakdown of Cookie Clicker's heavenly chips system and ascension upgrade tree.",
            },
        ],
    }
    path = tmp_path / "test_brief.json"
    path.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    return path, brief


@pytest.fixture
def valid_script_json():
    """Return a valid script JSON structure matching the prompt contract."""
    return {
        "hook_short_script": " ".join(["word"] * 100),  # 100 words — within [90, 120]
        "mid_form_body": " ".join(["word"] * 500),  # 500 words — within [400, 650]
        "title_suggestion": "Why Resetting Everything in Idle Games Feels Like Winning",
        "tags": [
            "idle games",
            "clicker games",
            "prestige mechanics",
            "game design",
            "Cookie Clicker",
            "incremental games",
        ],
    }


# =============================================================================
# ANCHOR 1: WAL Mode Confirmation
# =============================================================================
class TestWALMode:
    """ADR-003: WAL mode must be unconditionally enabled."""

    def test_wal_mode_enabled_on_init(self, tmp_db):
        """Verify PRAGMA journal_mode=WAL is active after database init."""
        conn = get_connection(tmp_db)
        result = conn.execute("PRAGMA journal_mode;").fetchone()
        conn.close()
        assert result[0] == "wal", f"Expected WAL mode, got: {result[0]}"

    def test_wal_mode_persists_on_reconnect(self, tmp_db):
        """WAL mode should persist across connections (SQLite WAL is per-file)."""
        conn1 = get_connection(tmp_db)
        conn1.close()
        conn2 = get_connection(tmp_db)
        result = conn2.execute("PRAGMA journal_mode;").fetchone()
        conn2.close()
        assert result[0] == "wal"


# =============================================================================
# ANCHOR 2: Schema Version Check
# =============================================================================
class TestSchemaVersion:
    """Schema version must be tracked and retrievable."""

    def test_schema_version_is_positive_integer(self):
        """SCHEMA_VERSION must be a positive integer."""
        assert isinstance(SCHEMA_VERSION, int)
        assert SCHEMA_VERSION >= 1

    def test_check_schema_version_returns_current(self, tmp_db):
        """check_schema_version must return the current SCHEMA_VERSION."""
        conn = get_connection(tmp_db)
        version = check_schema_version(conn)
        conn.close()
        assert version == SCHEMA_VERSION


# =============================================================================
# ANCHOR 3: Schema Table Existence
# =============================================================================
class TestSchemaStructure:
    """All four core tables per SDD Section 3.2 must exist after init."""

    def test_topics_table_exists(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='topics'"
        ).fetchone()
        conn.close()
        assert tables is not None, "topics table missing"

    def test_sources_table_exists(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sources'"
        ).fetchone()
        conn.close()
        assert tables is not None, "sources table missing"

    def test_scripts_table_exists(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scripts'"
        ).fetchone()
        conn.close()
        assert tables is not None, "scripts table missing"

    def test_asset_briefs_table_exists(self, tmp_db):
        conn = get_connection(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_briefs'"
        ).fetchone()
        conn.close()
        assert tables is not None, "asset_briefs table missing"


# =============================================================================
# ANCHOR 4: Manual Brief Loading
# =============================================================================
class TestManualBriefLoading:
    """ADR-001: Manual Brief Mode loads JSON into topics + sources."""

    def test_load_brief_creates_topic(self, tmp_db, sample_brief):
        """Loading a brief must create a topic row with input_mode='manual_brief'."""
        json_path, brief_data = sample_brief
        topic_id = load_brief(json_path, db_path=tmp_db)

        conn = get_connection(tmp_db)
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["title"] == brief_data["title"]
        assert row["input_mode"] == "manual_brief"
        assert row["status"] == "scripting"

    def test_load_brief_creates_sources(self, tmp_db, sample_brief):
        """Loading a brief must create source rows for each source entry."""
        json_path, brief_data = sample_brief
        topic_id = load_brief(json_path, db_path=tmp_db)

        conn = get_connection(tmp_db)
        sources = conn.execute(
            "SELECT * FROM sources WHERE topic_id = ?", (topic_id,)
        ).fetchall()
        conn.close()

        assert len(sources) == len(brief_data["sources"])

    def test_load_brief_sets_scripting_status(self, tmp_db, sample_brief):
        """Manual brief topics must enter status='scripting' (ready for P3)."""
        json_path, _ = sample_brief
        topic_id = load_brief(json_path, db_path=tmp_db)

        conn = get_connection(tmp_db)
        row = conn.execute("SELECT status FROM topics WHERE id = ?", (topic_id,)).fetchone()
        conn.close()

        assert row["status"] == "scripting"


# =============================================================================
# ANCHOR 5: Manual Brief Validation
# =============================================================================
class TestManualBriefValidation:
    """Brief JSON must be validated before database insertion."""

    def test_missing_required_keys_rejected(self):
        """Briefs missing required keys must fail validation."""
        errors = validate_brief({"title": "Test"})  # Missing domain, angle, sources
        assert len(errors) > 0

    def test_invalid_domain_rejected(self):
        """Briefs with invalid domain values must fail validation."""
        errors = validate_brief({
            "title": "Test",
            "domain": "cooking",
            "angle": "Test angle",
            "sources": [{"source_type": "blog", "title": "T", "summary": "S"}],
        })
        assert any("domain" in e.lower() for e in errors)

    def test_empty_sources_rejected(self):
        """Briefs with an empty sources array must fail validation."""
        errors = validate_brief({
            "title": "Test",
            "domain": "game_mechanics",
            "angle": "Test angle",
            "sources": [],
        })
        assert any("sources" in e.lower() for e in errors)

    def test_invalid_json_file_raises(self, tmp_path, tmp_db):
        """Non-JSON files must raise ManualBriefError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json {{{", encoding="utf-8")
        with pytest.raises(ManualBriefError, match="Invalid JSON"):
            load_brief(bad_file, db_path=tmp_db)


# =============================================================================
# ANCHOR 6: JSON Script Structure Validation
# =============================================================================
class TestScriptStructureValidation:
    """ADR-002: Script JSON must match the prompt contract structure."""

    def test_valid_script_passes(self, valid_script_json):
        """A correctly structured script JSON must pass validation."""
        errors = validate_script_json(valid_script_json)
        assert errors == []

    def test_missing_keys_detected(self):
        """Script JSON missing required keys must fail."""
        errors = validate_script_json({"hook_short_script": "test"})
        assert any("Missing required keys" in e for e in errors)

    def test_empty_hook_rejected(self, valid_script_json):
        """Empty hook_short_script must fail validation."""
        valid_script_json["hook_short_script"] = ""
        errors = validate_script_json(valid_script_json)
        assert len(errors) > 0


# =============================================================================
# ANCHOR 7: Hook Word Count Bounds (90-120)
# =============================================================================
class TestHookWordCountBounds:
    """hook_short_script must be 90-120 words per prompt contract."""

    def test_hook_below_minimum_rejected(self, valid_script_json):
        """Hook with fewer than 90 words must fail."""
        valid_script_json["hook_short_script"] = " ".join(["word"] * 50)
        errors = validate_script_json(valid_script_json)
        assert any("word count" in e.lower() and "hook" in e.lower() for e in errors)

    def test_hook_above_maximum_rejected(self, valid_script_json):
        """Hook with more than 120 words must fail."""
        valid_script_json["hook_short_script"] = " ".join(["word"] * 150)
        errors = validate_script_json(valid_script_json)
        assert any("word count" in e.lower() and "hook" in e.lower() for e in errors)

    def test_hook_at_minimum_accepted(self, valid_script_json):
        """Hook with exactly 90 words must pass."""
        valid_script_json["hook_short_script"] = " ".join(["word"] * HOOK_WORD_MIN)
        errors = validate_script_json(valid_script_json)
        assert not any("hook" in e.lower() for e in errors)

    def test_hook_at_maximum_accepted(self, valid_script_json):
        """Hook with exactly 120 words must pass."""
        valid_script_json["hook_short_script"] = " ".join(["word"] * HOOK_WORD_MAX)
        errors = validate_script_json(valid_script_json)
        assert not any("hook" in e.lower() for e in errors)


# =============================================================================
# ANCHOR 8: Body Word Count Bounds (400-650)
# =============================================================================
class TestBodyWordCountBounds:
    """mid_form_body must be 400-650 words per prompt contract."""

    def test_body_below_minimum_rejected(self, valid_script_json):
        """Body with fewer than 400 words must fail."""
        valid_script_json["mid_form_body"] = " ".join(["word"] * 100)
        errors = validate_script_json(valid_script_json)
        assert any("word count" in e.lower() and "body" in e.lower() for e in errors)

    def test_body_above_maximum_rejected(self, valid_script_json):
        """Body with more than 650 words must fail."""
        valid_script_json["mid_form_body"] = " ".join(["word"] * 700)
        errors = validate_script_json(valid_script_json)
        assert any("word count" in e.lower() and "body" in e.lower() for e in errors)


# =============================================================================
# ANCHOR 9: Forbidden Phrases in Body (ADR-002)
# =============================================================================
class TestForbiddenBodyPhrases:
    """mid_form_body must not reference the hook per ADR-002."""

    @pytest.mark.parametrize("phrase", FORBIDDEN_BODY_PHRASES)
    def test_forbidden_phrase_detected(self, valid_script_json, phrase):
        """Each forbidden phrase must be caught by validation."""
        body_words = ["word"] * 499
        body_words.append(phrase)
        valid_script_json["mid_form_body"] = " ".join(body_words)
        errors = validate_script_json(valid_script_json)
        assert any("forbidden" in e.lower() for e in errors)


# =============================================================================
# ANCHOR 10: Tags and Title Validation
# =============================================================================
class TestTagsAndTitleValidation:
    """Tags and title_suggestion must meet prompt contract requirements."""

    def test_tags_too_few_rejected(self, valid_script_json):
        """Fewer than 5 tags must fail."""
        valid_script_json["tags"] = ["a", "b", "c"]
        errors = validate_script_json(valid_script_json)
        assert any("tags" in e.lower() for e in errors)

    def test_tags_too_many_rejected(self, valid_script_json):
        """More than 10 tags must fail."""
        valid_script_json["tags"] = [f"tag{i}" for i in range(15)]
        errors = validate_script_json(valid_script_json)
        assert any("tags" in e.lower() for e in errors)

    def test_title_too_long_rejected(self, valid_script_json):
        """Title exceeding 80 characters must fail."""
        valid_script_json["title_suggestion"] = "A" * 81
        errors = validate_script_json(valid_script_json)
        assert any("title" in e.lower() for e in errors)

    def test_title_at_max_accepted(self, valid_script_json):
        """Title at exactly 80 characters must pass."""
        valid_script_json["title_suggestion"] = "A" * 80
        errors = validate_script_json(valid_script_json)
        assert not any("title" in e.lower() for e in errors)

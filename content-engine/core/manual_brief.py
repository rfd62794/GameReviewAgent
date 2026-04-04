"""
ContentEngine Manual Brief Loader (P1/P2 Bypass)

SDD Reference: Section 2.1 (Manual Brief Mode), ADR-001
Loads a handcrafted JSON brief file into the topics and sources tables,
bypassing P1 (Brief Generation) and P2 (Research Execution) entirely.

Manual Brief Mode is a permanent feature — not a workaround.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from core.db import init_db, get_connection

# --- JSON Schema Definition ---
# Required top-level keys for a valid manual brief.
REQUIRED_BRIEF_KEYS = {"title", "domain", "angle", "sources"}

# Valid domain values per SDD Section 3.2
VALID_DOMAINS = {"game_mechanics", "game_design", "indie_dev"}

# Required keys for each source entry
REQUIRED_SOURCE_KEYS = {"source_type", "title", "summary"}

# Valid source types per SDD Section 3.2
VALID_SOURCE_TYPES = {
    "gdc", "wiki", "interview", "blog", "paper", "reddit", "creator", "other"
}


class ManualBriefError(Exception):
    """Raised when a manual brief JSON file is invalid."""
    pass


def validate_brief(data: dict) -> list[str]:
    """
    Validate a parsed manual brief JSON structure.
    
    Args:
        data: Parsed JSON dict from the brief file.
    
    Returns:
        List of validation error strings. Empty list = valid.
    """
    errors = []

    # Check top-level required keys
    missing_keys = REQUIRED_BRIEF_KEYS - set(data.keys())
    if missing_keys:
        errors.append(f"Missing required top-level keys: {sorted(missing_keys)}")

    # Validate domain
    domain = data.get("domain")
    if domain and domain not in VALID_DOMAINS:
        errors.append(
            f"Invalid domain '{domain}'. Must be one of: {sorted(VALID_DOMAINS)}"
        )

    # Validate title is non-empty string
    title = data.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        errors.append("'title' must be a non-empty string.")

    # Validate angle is a string (nullable in DB but required in manual brief)
    angle = data.get("angle")
    if angle is not None and not isinstance(angle, str):
        errors.append("'angle' must be a string.")

    # Validate sources array
    sources = data.get("sources")
    if sources is not None:
        if not isinstance(sources, list):
            errors.append("'sources' must be an array.")
        elif len(sources) == 0:
            errors.append("'sources' must contain at least one entry.")
        else:
            for i, src in enumerate(sources):
                if not isinstance(src, dict):
                    errors.append(f"sources[{i}] must be an object.")
                    continue

                missing_src_keys = REQUIRED_SOURCE_KEYS - set(src.keys())
                if missing_src_keys:
                    errors.append(
                        f"sources[{i}] missing keys: {sorted(missing_src_keys)}"
                    )

                src_type = src.get("source_type")
                if src_type and src_type not in VALID_SOURCE_TYPES:
                    errors.append(
                        f"sources[{i}] invalid source_type '{src_type}'. "
                        f"Must be one of: {sorted(VALID_SOURCE_TYPES)}"
                    )

    # Validate optional notes field
    notes = data.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("'notes' must be a string if provided.")

    return errors


def load_brief(json_path: str | Path, db_path: Path | None = None) -> int:
    """
    Load a manual brief JSON file into the database.
    
    Parses JSON, validates structure, inserts into topics and sources tables
    with input_mode='manual_brief' and status='scripting' (ready for P3).
    
    Args:
        json_path: Path to the manual brief JSON file.
        db_path: Override database path (used in tests).
    
    Returns:
        topic_id of the newly created topic row.
    
    Raises:
        ManualBriefError: If JSON parsing or validation fails.
        FileNotFoundError: If json_path does not exist.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Brief file not found: {path}")

    # Parse JSON
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ManualBriefError(f"Invalid JSON in {path.name}: {e}") from e

    if not isinstance(data, dict):
        raise ManualBriefError("Brief JSON root must be an object, not an array.")

    # Validate structure
    errors = validate_brief(data)
    if errors:
        error_msg = f"Brief validation failed with {len(errors)} error(s):\n"
        for err in errors:
            error_msg += f"  - {err}\n"
        raise ManualBriefError(error_msg)

    # Insert into database
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        cursor = conn.execute(
            """
            INSERT INTO topics (title, domain, input_mode, angle, notes, status, created_at, updated_at)
            VALUES (?, ?, 'manual_brief', ?, ?, 'scripting', ?, ?)
            """,
            (
                data["title"],
                data["domain"],
                data.get("angle"),
                data.get("notes"),
                now,
                now,
            ),
        )
        topic_id = cursor.lastrowid

        # Insert sources
        for src in data["sources"]:
            conn.execute(
                """
                INSERT INTO sources (topic_id, source_type, title, url, summary, used_in_script, retrieved_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    topic_id,
                    src["source_type"],
                    src["title"],
                    src.get("url"),
                    src["summary"],
                    now,
                ),
            )

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise ManualBriefError(f"Database insert failed: {e}") from e
    finally:
        conn.close()

    return topic_id

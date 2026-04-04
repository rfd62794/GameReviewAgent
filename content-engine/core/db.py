"""
ContentEngine database initialization and access.

SDD Reference: Section 3.1, ADR-003
- WAL mode unconditionally enabled at init.
- Schema version checked at startup.
- Database file: database/content_engine.db (gitignored)
- Schema file: database/schema.sql (version controlled)
"""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

# Resolve paths relative to the project root (content-engine/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _PROJECT_ROOT / "database" / "content_engine.db"
SCHEMA_PATH = _PROJECT_ROOT / "database" / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Open a connection to the ContentEngine database.
    
    WAL mode is set unconditionally per ADR-003.
    Foreign keys are enforced.
    
    Args:
        db_path: Override database path (used in tests).
    
    Returns:
        sqlite3.Connection with WAL and FK enforcement enabled.
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # ADR-003: WAL unconditionally
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """
    Initialize the database: create tables from schema.sql if needed.
    
    Args:
        db_path: Override database path (used in tests).
    
    Returns:
        sqlite3.Connection ready for use.
    """
    conn = get_connection(db_path)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    return conn


def check_schema_version(conn: sqlite3.Connection) -> int:
    """
    Return the current SCHEMA_VERSION constant.
    
    Future: compare against a stored version in the DB and migrate if needed.
    """
    return SCHEMA_VERSION

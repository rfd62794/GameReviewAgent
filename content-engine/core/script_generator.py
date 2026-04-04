"""
ContentEngine P3 Script Generator

SDD Reference: Section 2.2 (P3 Script Drafting), Section 2.3 (ADR-002)
Calls Claude Sonnet via Anthropic API with the prompt contract defined in
prompts/script_generation.md. Validates JSON response structure and writes
to the scripts table.

External Dependency: anthropic Python SDK
Environment Variable: ANTHROPIC_API_KEY
"""

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import yaml

from core.db import get_connection

# --- Constants ---
MAX_TOKENS = 2048

# Word count bounds per ADR-002 and prompt contract
HOOK_WORD_MIN = 90
HOOK_WORD_MAX = 120
BODY_WORD_MIN = 400
BODY_WORD_MAX = 650

# Estimated speaking rate: ~2.5 words/second for natural narration
WORDS_PER_SECOND = 2.5

# Phrases forbidden in mid_form_body (case-insensitive check)
FORBIDDEN_BODY_PHRASES = [
    "as i mentioned",
    "as we discussed",
    "like i said",
    "that question",
    "in the intro",
    "earlier in this video",
    "as we said",
]

# Project paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_CONTRACT_PATH = _PROJECT_ROOT / "prompts" / "script_generation.md"
MODELS_CONFIG_PATH = _PROJECT_ROOT / "models.yaml"


def load_model_config() -> dict:
    """
    Load model configuration from models.yaml.
    
    Returns:
        Dict with model config including 'models' and 'routing' keys.
    """
    if not MODELS_CONFIG_PATH.exists():
        raise ScriptGenerationError(
            f"Model config not found: {MODELS_CONFIG_PATH}"
        )
    with open(MODELS_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_model_string(config: dict, stage: str = "p3_scripting") -> str:
    """
    Resolve the API model string for a given pipeline stage.
    
    For direct routing (Anthropic SDK), strips the provider prefix.
    For OpenRouter routing, returns the full prefixed string.
    
    Args:
        config: Parsed models.yaml dict.
        stage: Pipeline stage key (e.g., 'p3_scripting').
    
    Returns:
        Model string suitable for the target API.
    """
    canonical = config["models"][stage]  # e.g., "anthropic/claude-sonnet-4-6"
    routing = config.get("routing", {}).get(stage, "direct")
    
    if routing == "direct":
        # Strip provider prefix for direct SDK calls
        # "anthropic/claude-sonnet-4-6" -> "claude-sonnet-4-6"
        if "/" in canonical:
            return canonical.split("/", 1)[1]
        return canonical
    else:
        # OpenRouter expects the full prefixed string
        return canonical


class ScriptGenerationError(Exception):
    """Raised when script generation or validation fails."""
    pass


class ScriptValidationError(ScriptGenerationError):
    """Raised when the LLM response fails structural validation."""
    pass


def _count_words(text: str) -> int:
    """Count words in a text string."""
    return len(text.split())


def validate_script_json(data: dict) -> list[str]:
    """
    Validate the JSON structure returned by the LLM against the prompt contract.
    
    Args:
        data: Parsed JSON dict from LLM response.
    
    Returns:
        List of validation error strings. Empty list = valid.
    """
    errors = []

    # Check required keys
    required_keys = {"hook_short_script", "mid_form_body", "title_suggestion", "tags"}
    missing = required_keys - set(data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(missing)}")
        return errors  # Can't validate further without required fields

    # Validate hook_short_script
    hook = data["hook_short_script"]
    if not isinstance(hook, str) or not hook.strip():
        errors.append("hook_short_script must be a non-empty string.")
    else:
        hook_wc = _count_words(hook)
        if hook_wc < HOOK_WORD_MIN or hook_wc > HOOK_WORD_MAX:
            errors.append(
                f"hook_short_script word count {hook_wc} outside bounds "
                f"[{HOOK_WORD_MIN}, {HOOK_WORD_MAX}]."
            )

    # Validate mid_form_body
    body = data["mid_form_body"]
    if not isinstance(body, str) or not body.strip():
        errors.append("mid_form_body must be a non-empty string.")
    else:
        body_wc = _count_words(body)
        if body_wc < BODY_WORD_MIN or body_wc > BODY_WORD_MAX:
            errors.append(
                f"mid_form_body word count {body_wc} outside bounds "
                f"[{BODY_WORD_MIN}, {BODY_WORD_MAX}]."
            )

        # Check forbidden phrases
        body_lower = body.lower()
        for phrase in FORBIDDEN_BODY_PHRASES:
            if phrase in body_lower:
                errors.append(
                    f"mid_form_body contains forbidden phrase: '{phrase}'"
                )

    # Validate title_suggestion
    title = data.get("title_suggestion")
    if not isinstance(title, str) or not title.strip():
        errors.append("title_suggestion must be a non-empty string.")
    elif len(title) > 80:
        errors.append(f"title_suggestion length {len(title)} exceeds 80 char limit.")

    # Validate tags
    tags = data.get("tags")
    if not isinstance(tags, list):
        errors.append("tags must be an array.")
    elif not all(isinstance(t, str) for t in tags):
        errors.append("All tags must be strings.")
    elif len(tags) < 5 or len(tags) > 10:
        errors.append(f"tags count {len(tags)} outside bounds [5, 10].")

    return errors


def _build_system_prompt() -> str:
    """Build the system prompt from the prompt contract preamble."""
    return (
        "You are a YouTube script writer specializing in game mechanics analysis. "
        "You write engaging, research-backed scripts that explain game design concepts "
        "to an audience of curious gamers and aspiring developers.\n\n"
        "You produce TWO strictly separated script segments as a JSON object. These "
        "segments serve different distribution formats and MUST be fully independent "
        "of each other.\n\n"
        "CRITICAL RULES:\n"
        "1. Respond with a SINGLE valid JSON object. No markdown fences. No preamble.\n"
        "2. hook_short_script: 90-120 words, self-contained Short. No forward references.\n"
        "3. mid_form_body: 400-650 words, body only. NEVER reference the hook.\n"
        "4. Forbidden in mid_form_body: 'as I mentioned', 'as we discussed', "
        "'like I said', 'that question', 'in the intro', 'earlier in this video', "
        "'as we said'.\n"
        "5. These are TWO INDEPENDENT writings, not a split monolith."
    )


def _build_user_prompt(topic: dict, sources: list[dict]) -> str:
    """
    Build the user prompt from topic data and sources.
    
    Args:
        topic: Dict with keys from topics table row.
        sources: List of dicts from sources table rows.
    
    Returns:
        Formatted user prompt string.
    """
    formatted_sources = ""
    for i, src in enumerate(sources, 1):
        formatted_sources += f"{i}. [{src['source_type']}] {src['title']}"
        if src.get("url"):
            formatted_sources += f" — {src['url']}"
        formatted_sources += f"\n   {src['summary']}\n"

    if not formatted_sources.strip():
        formatted_sources = "No external sources provided. Use general knowledge."

    notes = topic.get("notes") or "None provided."

    return (
        f"Write a YouTube script about the following topic:\n\n"
        f"**Topic:** {topic['title']}\n"
        f"**Angle:** {topic.get('angle', 'General overview')}\n"
        f"**Domain:** {topic['domain']}\n\n"
        f"**Research Sources:**\n{formatted_sources}\n"
        f"**Additional Notes:**\n{notes}\n\n"
        f"Remember: hook_short_script and mid_form_body are SEPARATE distribution formats.\n"
        f"The Short must stand alone. The body must not reference the hook.\n"
        f"Respond with valid JSON only. No markdown. No commentary."
    )


def generate_script(
    topic_id: int,
    db_path: Path | None = None,
    max_retries: int = 2,
) -> int:
    """
    Generate a script for a topic using Claude Sonnet.
    
    Fetches topic and sources from DB, calls the LLM with the prompt contract,
    validates the response, and writes to the scripts table.
    
    Args:
        topic_id: ID of the topic to generate a script for.
        db_path: Override database path (used in tests).
        max_retries: Number of retry attempts on validation failure.
    
    Returns:
        script_id of the newly created scripts row.
    
    Raises:
        ScriptGenerationError: If API call fails or retries exhausted.
        ScriptValidationError: If LLM response fails validation after all retries.
    """
    # Lazy import — only needed when actually calling the API
    try:
        import anthropic
    except ImportError:
        raise ScriptGenerationError(
            "anthropic package not installed. Run: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ScriptGenerationError(
            "ANTHROPIC_API_KEY environment variable not set."
        )

    conn = get_connection(db_path)

    try:
        # Fetch topic
        row = conn.execute(
            "SELECT * FROM topics WHERE id = ?", (topic_id,)
        ).fetchone()
        if not row:
            raise ScriptGenerationError(f"Topic {topic_id} not found.")

        topic = dict(row)

        # Fetch sources
        source_rows = conn.execute(
            "SELECT * FROM sources WHERE topic_id = ?", (topic_id,)
        ).fetchall()
        sources = [dict(s) for s in source_rows]

        # Build prompts
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(topic, sources)

        # Load model config and resolve model string
        config = load_model_config()
        model = _resolve_model_string(config, "p3_scripting")

        # Call Claude Sonnet
        client = anthropic.Anthropic(api_key=api_key)
        last_errors = []

        for attempt in range(1, max_retries + 1):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )

                # Extract text content
                raw_text = response.content[0].text.strip()

                # Parse JSON
                try:
                    script_data = json.loads(raw_text)
                except json.JSONDecodeError as e:
                    last_errors.append(f"Attempt {attempt}: Invalid JSON — {e}")
                    continue

                # Validate
                validation_errors = validate_script_json(script_data)
                if validation_errors:
                    last_errors.append(
                        f"Attempt {attempt}: Validation failed — "
                        + "; ".join(validation_errors)
                    )
                    continue

                # Validation passed — write to DB
                hook_wc = _count_words(script_data["hook_short_script"])
                body_wc = _count_words(script_data["mid_form_body"])
                total_words = hook_wc + body_wc
                est_duration = int(total_words / WORDS_PER_SECOND)

                # Get next version number for this topic
                ver_row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS next_ver "
                    "FROM scripts WHERE topic_id = ?",
                    (topic_id,),
                ).fetchone()
                next_version = ver_row["next_ver"]

                now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                cursor = conn.execute(
                    """
                    INSERT INTO scripts 
                        (topic_id, version, hook_short_script, mid_form_body,
                         word_count_hook, word_count_body, estimated_duration_s,
                         approved, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        topic_id,
                        next_version,
                        script_data["hook_short_script"],
                        script_data["mid_form_body"],
                        hook_wc,
                        body_wc,
                        est_duration,
                        now,
                    ),
                )
                script_id = cursor.lastrowid

                # Update topic status
                conn.execute(
                    "UPDATE topics SET status = 'ready', updated_at = ? WHERE id = ?",
                    (now, topic_id),
                )

                conn.commit()
                return script_id

            except anthropic.APIError as e:
                last_errors.append(f"Attempt {attempt}: API error — {e}")
                continue

        # All retries exhausted
        error_log = "\n".join(last_errors)
        raise ScriptValidationError(
            f"Script generation failed after {max_retries} attempts:\n{error_log}"
        )

    finally:
        conn.close()

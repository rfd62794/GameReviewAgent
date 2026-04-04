"""
ContentEngine P3 — First Script Generation Run

Director-authorized generation run.
Loads idle clicker prestige brief → calls Claude Sonnet via OpenRouter →
validates response → writes to scripts table → prints for Director review.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.db import init_db, get_connection
from core.manual_brief import load_brief
from core.llm_client import OpenRouterLLMAdapter, LLMError
from core.script_generator import (
    validate_script_json,
    _build_system_prompt,
    _build_user_prompt,
    _count_words,
    HOOK_WORD_MIN,
    HOOK_WORD_MAX,
    BODY_WORD_MIN,
    BODY_WORD_MAX,
    WORDS_PER_SECOND,
    load_model_config,
)

BRIEF_PATH = Path(__file__).resolve().parent / "briefs" / "idle_clicker_prestige.json"


def main():
    print("=" * 70)
    print("ContentEngine P3 — First Script Generation Run")
    print("=" * 70)
    print()

    # --- Step 1: Initialize DB and load brief ---
    print("[1/4] Initializing database...")
    conn = init_db()
    conn.close()

    print(f"[2/4] Loading brief: {BRIEF_PATH.name}")
    topic_id = load_brief(BRIEF_PATH)
    print(f"       Topic ID: {topic_id}")
    print(f"       Status: scripting (ready for P3)")

    # --- Step 2: Fetch topic + sources from DB ---
    conn = get_connection()
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    topic = dict(row)
    source_rows = conn.execute(
        "SELECT * FROM sources WHERE topic_id = ?", (topic_id,)
    ).fetchall()
    sources = [dict(s) for s in source_rows]
    print(f"       Sources loaded: {len(sources)}")
    print()

    # --- Step 3: Build prompts and call LLM ---
    print("[3/4] Generating script via OpenRouter...")
    config = load_model_config()
    model = config["models"]["p3_scripting"]
    print(f"       Model: {model}")

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(topic, sources)

    client = OpenRouterLLMAdapter(model=model)

    retries = 0
    max_attempts = 3
    script_data = None
    warnings = []

    for attempt in range(1, max_attempts + 1):
        print(f"       Attempt {attempt}/{max_attempts}...")
        try:
            result = client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=2048,
                temperature=0.7,
            )

            raw_text = result["text"].strip()

            # Parse JSON
            try:
                script_data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                warnings.append(f"Attempt {attempt}: Invalid JSON — {e}")
                print(f"       ⚠ Invalid JSON response, retrying...")
                continue

            # Validate
            validation_errors = validate_script_json(script_data)
            if validation_errors:
                for err in validation_errors:
                    warnings.append(f"Attempt {attempt}: {err}")
                    print(f"       ⚠ {err}", flush=True)
                print(f"       Retrying...", flush=True)
                script_data = None
                continue

            # Success
            retries = attempt - 1
            print(f"       ✓ Valid script received on attempt {attempt}")
            break

        except LLMError as e:
            warnings.append(f"Attempt {attempt}: LLM error — {e}")
            print(f"       ⚠ LLM error: {e}")
            continue

    if script_data is None:
        print("\n✗ FAILED: Could not generate valid script after all attempts.")
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
        conn.close()
        sys.exit(1)

    # --- Step 4: Write to database ---
    print("[4/4] Writing to scripts table...")
    hook_wc = _count_words(script_data["hook_short_script"])
    body_wc = _count_words(script_data["mid_form_body"])
    total_words = hook_wc + body_wc
    est_duration = int(total_words / WORDS_PER_SECOND)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    cursor = conn.execute(
        """
        INSERT INTO scripts 
            (topic_id, version, hook_short_script, mid_form_body,
             word_count_hook, word_count_body, estimated_duration_s,
             approved, created_at)
        VALUES (?, 1, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            topic_id,
            script_data["hook_short_script"],
            script_data["mid_form_body"],
            hook_wc,
            body_wc,
            est_duration,
            now,
        ),
    )
    script_id = cursor.lastrowid

    conn.execute(
        "UPDATE topics SET status = 'ready', updated_at = ? WHERE id = ?",
        (now, topic_id),
    )
    conn.commit()
    conn.close()

    print(f"       Script ID: {script_id}")
    print()

    # --- Output for Director Review ---
    print("=" * 70)
    print("DIRECTOR REVIEW — SCRIPT OUTPUT")
    print("=" * 70)
    print()

    print("─── hook_short_script ───")
    print()
    print(script_data["hook_short_script"])
    print()
    print(f"  Word count: {hook_wc} (bounds: {HOOK_WORD_MIN}–{HOOK_WORD_MAX})")
    print()

    print("─── mid_form_body ───")
    print()
    print(script_data["mid_form_body"])
    print()
    print(f"  Word count: {body_wc} (bounds: {BODY_WORD_MIN}–{BODY_WORD_MAX})")
    print()

    print("─── metadata ───")
    print()
    print(f"  Title suggestion: {script_data.get('title_suggestion', 'N/A')}")
    print(f"  Tags: {script_data.get('tags', [])}")
    print(f"  Estimated duration: {est_duration}s ({est_duration // 60}m {est_duration % 60}s)")
    print(f"  Retries: {retries}")
    print()

    if warnings:
        print("─── warnings ───")
        print()
        for w in warnings:
            print(f"  ⚠ {w}")
        print()

    print("=" * 70)
    print("GENERATION COMPLETE — Awaiting Director review.")
    print("Do not proceed to P6 (audio) without approval.")
    print("=" * 70)


if __name__ == "__main__":
    main()

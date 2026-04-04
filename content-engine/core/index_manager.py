import json
import logging
import re
from pathlib import Path

from core.db import get_connection
from core.llm_client import create_llm_client

logger = logging.getLogger(__name__)

def lookup(game_title: str, mechanic: str) -> list[str]:
    """Retrieve search queries for game and mechanic, ordered by confidence & success."""
    conn = get_connection()
    cursor = conn.execute(
        """
        SELECT search_query FROM game_clip_index 
        WHERE game_title = ? AND mechanic = ? AND verified = 1
        ORDER BY times_successful DESC, confidence_avg DESC
        """,
        (game_title, mechanic)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def record_attempt(game_title: str, mechanic: str, query: str, channel: str | None):
    """Log an attempt using a query in the index."""
    conn = get_connection()
    # Check if exists
    cursor = conn.execute(
        "SELECT id FROM game_clip_index WHERE game_title = ? AND mechanic = ? AND search_query = ?",
        (game_title, mechanic, query)
    )
    row = cursor.fetchone()
    
    if row:
        conn.execute(
            "UPDATE game_clip_index SET times_attempted = times_attempted + 1, last_used_at = datetime('now') WHERE id = ?",
            (row[0],)
        )
    else:
        conn.execute(
            """
            INSERT INTO game_clip_index (game_title, mechanic, search_query, channel, times_attempted, last_used_at) 
            VALUES (?, ?, ?, ?, 1, datetime('now'))
            """,
            (game_title, mechanic, query, channel)
        )
    conn.commit()
    conn.close()

def record_success(game_title: str, mechanic: str, query: str, channel: str | None, confidence: float, segment_text: str):
    """Log a successful hit, updating moving averages and triggering index expansion."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT id, times_successful, confidence_avg FROM game_clip_index WHERE game_title = ? AND mechanic = ? AND search_query = ?",
        (game_title, mechanic, query)
    )
    row = cursor.fetchone()
    
    if row:
        idx, old_successes, old_avg = row
        new_successes = old_successes + 1
        # Simple rolling average recalculation
        new_avg = ((old_avg * old_successes) + confidence) / new_successes
        
        conn.execute(
            """
            UPDATE game_clip_index 
            SET times_successful = ?, confidence_avg = ?, verified = 1, last_used_at = datetime('now')
            WHERE id = ?
            """,
            (new_successes, new_avg, idx)
        )
    conn.commit()
    conn.close()
    
    # Trigger expansion asynchronously or block execution (as specified, it calls it)
    expand_index(game_title, mechanic, segment_text, query, channel)

def expand_index(game_title: str, mechanic: str, segment_text: str, accepted_query: str, accepted_channel: str | None):
    """Use the LLM updater to expand queries upon success."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "index_updater.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()
    except FileNotFoundError:
        logger.error("Index updater prompt contract not found.")
        return

    formatted = sys_prompt.replace("{game_title}", game_title)
    formatted = formatted.replace("{mechanic}", mechanic)
    formatted = formatted.replace("{accepted_query}", accepted_query)
    formatted = formatted.replace("{accepted_channel}", str(accepted_channel))
    formatted = formatted.replace("{segment_text}", segment_text)

    client = create_llm_client(model="deepseek/deepseek-chat")
    try:
        response_dict = client.generate(
            system_prompt="You augment search index tables into strict JSON arrays.",
            prompt=formatted,
            temperature=0.0
        )
        response_text = response_dict.get("text", "")
        cleaned = re.sub(r'```json|```', '', response_text).strip()
        # Since this output contains nested dict inside lists, use looser dotall:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if not match:
            return
            
        data = json.loads(match.group())
        
        conn = get_connection()
        for new_query in data.get("additional_queries", []):
            try:
                conn.execute(
                    """
                    INSERT INTO game_clip_index (game_title, mechanic, search_query, verified, suggested_by) 
                    VALUES (?, ?, ?, 0, 'llm_updater')
                    """,
                    (game_title, mechanic, new_query)
                )
            except Exception:
                pass # skip duplicates if unique constraints existed, or errors

        for related in data.get("related_mechanics", []):
            rel_mech = related.get("mechanic")
            rel_query = related.get("search_query")
            if rel_mech and rel_query:
                try:
                    conn.execute(
                        """
                        INSERT INTO game_clip_index (game_title, mechanic, search_query, verified, suggested_by) 
                        VALUES (?, ?, ?, 0, 'llm_updater_related')
                        """,
                        (game_title, rel_mech, rel_query)
                    )
                except Exception:
                    pass
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Index expansion LLM failed: {e}")

def suggest_new_entries(script_text: str) -> int:
    """Post-run script evaluation to suggest new mechanics to track."""
    # STUB: To be fully implemented when P7 finishes entire script orchestrations.
    # Returns count of suggestions added.
    return 0

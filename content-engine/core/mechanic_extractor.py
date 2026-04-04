import json
import logging
import re
from pathlib import Path

from core.llm_client import create_llm_client

logger = logging.getLogger(__name__)

def extract(segment_text: str) -> dict:
    """Extract game names, mechanic, visual moment, and search queries from script segment text."""
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "mechanic_extractor.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            sys_prompt = f.read()
    except FileNotFoundError:
        logger.error("Mechanic extractor prompt contract not found.")
        return {"games": [], "mechanic": "unknown", "moment": "gameplay", "search_queries": []}

    formatted = sys_prompt.replace("{segment_text}", segment_text)

    client = create_llm_client(model="deepseek/deepseek-chat")
    try:
        response_dict = client.generate(
            system_prompt="You extract metadata to structured JSON schema.",
            prompt=formatted,
            temperature=0.0
        )
        response_text = response_dict.get("text", "")
        
        # Strip code fences if present
        cleaned = re.sub(r'```json|```', '', response_text).strip()
        
        # Find outermost JSON object
        match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
        if not match:
            # Maybe it contains arrays inside, doing a looser extract as fallback:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            
        if not match:
            logger.error("No JSON object found in LLM extraction response")
            return {"games": [], "mechanic": "unknown", "moment": "gameplay", "search_queries": []}
            
        return json.loads(match.group())
        
    except Exception as e:
        logger.error(f"LLM mechanic extraction failed: {e}")
        return {"games": [], "mechanic": "unknown", "moment": "gameplay", "search_queries": []}

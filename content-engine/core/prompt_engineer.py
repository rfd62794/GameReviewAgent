import logging
from typing import Optional
from core.llm_client import create_llm_client

logger = logging.getLogger(__name__)

# OpenRouter model for prompt engineering (DeepSeek is fast and cheap)
PROMPT_ENGINEER_MODEL = "deepseek/deepseek-chat"

SYSTEM_PROMPT = """You are an expert at writing prompts for AI image generation models. 
You write prompts that produce game-accurate, visually specific results.

Given a game title, mechanic, and moment to depict, write a single image generation prompt that:
- Describes what is VISUALLY ON SCREEN in detail
- Uses the game's actual art style terminology (as provided in style notes)
- Specifies lighting, color palette, UI elements, and composition
- Is 50-100 words maximum
- Contains NO abstract concepts — only visual elements
- Never mentions the mechanic name in snake_case (e.g. use "prestige reset" not "prestige_reset")

Output the prompt only. No preamble. No explanation."""

def generate_visual_prompt(
    game_title: str, 
    mechanic: str, 
    moment: str, 
    style_notes: Optional[str] = None
) -> str:
    """
    Use an LLM (typically DeepSeek) to generate a high-fidelity visual prompt 
    based on game context and style notes.
    """
    # Normalize mechanic
    mech_norm = mechanic.replace("_", " ") if mechanic else ""
    
    user_content = f"Game: {game_title}\n"
    user_content += f"Mechanic: {mech_norm}\n"
    user_content += f"Visual Moment: {moment}\n"
    if style_notes:
        user_content += f"Game Style Notes: {style_notes}\n"
        
    user_content += "\nWrite an image generation prompt for this moment."

    client = create_llm_client(model=PROMPT_ENGINEER_MODEL)
    
    try:
        print(f"    [Prompt Engineer] Generating optimized prompt for {game_title}...")
        response = client.generate(
            prompt=user_content,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=300,
            response_format=None # Ensure text output, not JSON
        )
        
        optimized_prompt = response.get("text", "").strip()
        
        # Clean up any quotes if the model wrapped it
        if optimized_prompt.startswith('"') and optimized_prompt.endswith('"'):
            optimized_prompt = optimized_prompt[1:-1]
            
        return optimized_prompt
        
    except Exception as e:
        logger.error(f"Prompt engineering failed: {e}")
        # Fallback to a basic template if DeepSeek fails
        style = f", {style_notes}" if style_notes else ""
        return f"{game_title} {mech_norm}, {moment}, game UI screenshot style, 4K{style}"

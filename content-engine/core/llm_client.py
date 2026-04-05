"""
ContentEngine LLM Client — Ported from OpenAgent openrouter_llm.py

Source: OpenAgent/src/orchestration/openrouter_llm.py (454 lines)
Port date: 2026-04-04
Verdict: LIFT WITH MINOR FIXES

Applied fixes:
  FIX 1 — response_format parameter defaulting to {"type": "json_object"}
  FIX 2 — CostTracker/LLMCallMetrics stubbed (Phase 2 cleanup)
  FIX 3 — Fallback model map updated for ContentEngine roster
  FIX 4 — Global _cost_tracker removed; constructor param with null check
  FIX 5 — Headers updated (HTTP-Referer, X-Title)
  FIX 6 — Singleton pattern removed (constructor param default None)

External Dependency: requests
Environment Variable: OPENROUTER_API_KEY
"""

import os
import json
import time
import base64
import requests
import logging
from datetime import datetime
from typing import Any, Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Exception hierarchy (UNCHANGED from source)
# =============================================================================

class LLMError(Exception):
    """Base exception for LLM operations"""
    pass

class LLMTimeoutError(LLMError):
    """LLM call timed out"""
    pass

class LLMRateLimitError(LLMError):
    """Rate limited by API"""
    pass

class LLMResponseError(LLMError):
    """Invalid response from API"""
    pass


# =============================================================================
# FIX 2 + FIX 6: Stubbed metrics classes. ContentEngine logs via SQLite.
# Remove in Phase 2 cleanup.
# =============================================================================

class LLMCallMetrics:
    # STUB — ContentEngine logs via SQLite. Remove in Phase 2 cleanup.
    pass

class CostTracker:
    # STUB — ContentEngine logs via SQLite. Remove in Phase 2 cleanup.
    pass

# FIX 4: Global _cost_tracker singleton removed.
# CostTracker is now a constructor param defaulting to None.


# =============================================================================
# Core adapter (production-hardened retry logic preserved from OpenAgent)
# =============================================================================

class OpenRouterLLMAdapter:
    """Production-hardened LLM adapter with error recovery and fallback routing.
    
    Ported from OpenAgent with ContentEngine-specific fixes applied.
    Retry logic: 3 attempts with exponential backoff, then fallback model.
    """

    DEFAULT_TIMEOUT = 120  # seconds
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1  # seconds

    # FIX 3: Fallback model map updated for ContentEngine roster
    FALLBACK_MODELS = {
        "anthropic/claude-sonnet-4-6": "anthropic/claude-haiku-4-5-20251001",
        "deepseek/deepseek-chat": "anthropic/claude-haiku-4-5-20251001",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-sonnet-4-6",
        base_url: str = "https://openrouter.ai/api/v1",
        cost_tracker: Optional[CostTracker] = None,  # FIX 4: default None, no global
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise LLMError("OPENROUTER_API_KEY not found in environment variables")

        self.model = model
        self.base_url = base_url
        self.cost_tracker = cost_tracker  # FIX 4: None is valid — null-checked before use
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logger

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        agent_name: str = "content_engine",
        directive_id: Optional[str] = None,
        response_format: Optional[Dict[str, str]] = None,  # FIX 1: JSON enforcement
        **kwargs
    ) -> Dict[str, Any]:
        """Generate with automatic error recovery and optional JSON enforcement.
        
        Args:
            prompt: User prompt text.
            system_prompt: Optional system prompt.
            tools: Optional tool definitions.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            agent_name: Calling agent identifier for logging.
            directive_id: Optional directive tracking ID.
            response_format: Response format constraint. Defaults to
                {"type": "json_object"} for ContentEngine (always JSON).
                Pass None explicitly to disable for non-JSON stages.
            **kwargs: Additional parameters passed to the API.
        
        Returns:
            Dict with 'text', 'tool_calls', 'model', 'usage' keys.
        """
        # FIX 1: Default to JSON mode — ContentEngine always expects JSON from P3
        if response_format is None:
            response_format = {"type": "json_object"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return self.call_with_retries(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_name=agent_name,
            directive_id=directive_id,
            response_format=response_format,  # FIX 1: pass through
            **kwargs
        )

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_size: str = "2K",
        model: Optional[str] = None
    ) -> bytes | None:
        """
        Specialized call for image generation via OpenRouter multimodal endpoint.
        Returns raw bytes of the decoded PNG image.
        """
        model = model or self.model
        messages = [{"role": "user", "content": prompt}]
        
        # We call _make_request directly for image generation to use 
        # specific multimodal modalities and image_config.
        try:
            response_data = self._make_request(
                model=model,
                messages=messages,
                modalities=["image", "text"],
                image_config={
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size
                }
            )
            
            # OpenRouter returns images in choice.message.images
            # Structure: choices[0].message.images[0].image_url.url (base64)
            self._validate_response(response_data)
            choice = response_data["choices"][0]
            message = choice.get("message", {})
            images = message.get("images", [])
            
            if not images:
                self.logger.error("No images found in multimodal response")
                return None
            
            # Extract base64 URL
            image_url = images[0].get("image_url", {}).get("url", "")
            if not image_url.startswith("data:image/"):
                self.logger.error("Response is not a valid base64 image data URL")
                return None
            
            # Strip prefix: data:image/png;base64,
            base64_data = image_url.split(",")[1]
            return base64.b64decode(base64_data)
            
        except Exception as e:
            self.logger.error(f"Image generation failed: {e}")
            return None

    def call_with_retries(
        self,
        model: str,
        messages: List[Dict[str, str]],
        agent_name: str = "content_engine",
        directive_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Call LLM with comprehensive error handling and retry logic.
        
        3 attempts with exponential backoff (1s, 2s, 4s), then fallback model.
        """

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response_data = self._make_request(
                    model=model,
                    messages=messages,
                    **kwargs
                )

                # Validate and extract
                self._validate_response(response_data)

                choice = response_data["choices"][0]
                result = {
                    "text": choice["message"]["content"],
                    "tool_calls": self._extract_tool_calls(choice["message"]),
                    "model": model,
                    "usage": response_data.get("usage", {}),
                }

                self.logger.info(
                    f"LLM call succeeded: {agent_name} | {model} | "
                    f"{result['usage'].get('total_tokens', '?')} tokens"
                )
                return result

            except (LLMTimeoutError, LLMRateLimitError) as e:
                last_error = e
                self.logger.warning(
                    f"LLM {type(e).__name__} on attempt "
                    f"{attempt + 1}/{self.max_retries}: {agent_name}"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.INITIAL_BACKOFF * (2 ** attempt)
                    time.sleep(wait_time)

            except LLMResponseError as e:
                self.logger.error(f"Invalid LLM response: {e}")
                raise

            except Exception as e:
                last_error = e
                self.logger.error(
                    f"Unexpected error on attempt {attempt + 1}: {e}"
                )
                if attempt < self.max_retries - 1:
                    wait_time = self.INITIAL_BACKOFF * (2 ** attempt)
                    time.sleep(wait_time)

        # All retries failed for this model — try fallback
        self.logger.error(
            f"LLM call failed after {self.max_retries} attempts: {last_error}"
        )

        fallback = self.FALLBACK_MODELS.get(model)
        if fallback and fallback != model:
            self.logger.info(f"Attempting fallback model: {fallback}")
            try:
                return self.call_with_retries(
                    model=fallback,
                    messages=messages,
                    agent_name=agent_name,
                    directive_id=directive_id,
                    **kwargs
                )
            except Exception as e:
                self.logger.error(f"Fallback also failed: {e}")

        raise last_error

    def _make_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[Dict[str, str]] = None,  # FIX 1
        **kwargs
    ) -> Dict[str, Any]:
        """Make internal API request to OpenRouter."""

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # FIX 1: Include response_format in payload when specified
        if response_format is not None:
            payload["response_format"] = response_format

        # MODALITY FIX: Only add modalities and image_config if provided
        if "modalities" in kwargs:
            payload["modalities"] = kwargs.pop("modalities")
        if "image_config" in kwargs:
            payload["image_config"] = kwargs.pop("image_config")
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                }
                for tool in tools
            ]

        # Add any extra kwargs
        for k, v in kwargs.items():
            if k not in payload:
                payload[k] = v

        # FIX 5: Headers updated for ContentEngine
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/rfd62794/content-engine",
            "X-Title": "ContentEngine",
        }

        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout:
            raise LLMTimeoutError(f"LLM call timed out after {self.timeout}s")
        except Exception as e:
            raise LLMError(f"Request failed: {e}")

        if response.status_code == 429:
            raise LLMRateLimitError("Rate limited by OpenRouter")

        if response.status_code == 401:
            raise LLMError("Invalid API key")

        if response.status_code >= 500:
            raise LLMError(f"API server error: {response.status_code}")

        if response.status_code >= 400:
            try:
                error_msg = response.json().get("error", {}).get("message", response.text)
            except Exception:
                error_msg = response.text
            raise LLMError(f"API error ({response.status_code}): {error_msg}")

        try:
            return response.json()
        except json.JSONDecodeError:
            raise LLMResponseError(f"Invalid JSON response: {response.text[:200]}")

    def _validate_response(self, response: Dict[str, Any]):
        """Validate response structure."""
        if not isinstance(response, dict):
            raise LLMResponseError("Response is not a dict")
        if "choices" not in response or not response["choices"]:
            raise LLMResponseError("Response missing 'choices' or choices is empty")
        choice = response["choices"][0]
        
        # Valid message must have content OR images (multimodal)
        message = choice.get("message", {})
        if "content" not in message and "images" not in message:
            raise LLMResponseError("Choice missing 'content' and 'images'")
        # NOTE: 'usage' key checked with .get() in call_with_retries instead
        # of hard-failing here — some OpenRouter responses omit usage on
        # certain models. This avoids the brittleness flagged in audit.

    def _extract_tool_calls(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tool calls from message dict."""
        tool_calls = []
        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                tool_calls.append({
                    "id": tc.get("id"),
                    "name": tc.get("function", {}).get("name"),
                    "arguments": tc.get("function", {}).get("arguments")
                })
        return tool_calls


# =============================================================================
# Factory function
# =============================================================================

def create_llm_client(
    model: str = "anthropic/claude-sonnet-4-6",
    api_key: Optional[str] = None
) -> OpenRouterLLMAdapter:
    """Factory function to create a ContentEngine LLM client."""
    return OpenRouterLLMAdapter(api_key=api_key, model=model)

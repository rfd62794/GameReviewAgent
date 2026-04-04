"""
ContentEngine LLM Connection Tests

Tests in two tiers:
  Tier 1 — Offline: Config validation, model string resolution, 
           fallback map correctness. Always run.
  Tier 2 — Live (skipped without OPENROUTER_API_KEY): Ping OpenRouter
           with p3_scripting model, assert valid JSON response.

No API keys are hardcoded. All read from environment variables.
"""

import os
import json
import sys
from pathlib import Path

import pytest
import yaml

# Ensure content-engine root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm_client import (
    OpenRouterLLMAdapter,
    LLMError,
    LLMResponseError,
)
from core.script_generator import (
    load_model_config,
    _resolve_model_string,
    MODELS_CONFIG_PATH,
)

# Project root for direct YAML loading
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODELS_PATH = _PROJECT_ROOT / "models.yaml"


# =============================================================================
# TIER 1: Offline config validation (always runs)
# =============================================================================

class TestModelConfig:
    """Verify models.yaml is present and correctly structured."""

    def test_models_yaml_exists(self):
        """models.yaml must exist at project root."""
        assert _MODELS_PATH.exists(), f"Missing: {_MODELS_PATH}"

    def test_models_yaml_parses(self):
        """models.yaml must be valid YAML."""
        config = load_model_config()
        assert isinstance(config, dict)
        assert "models" in config

    def test_p3_model_string_present(self):
        """p3_scripting model must be defined."""
        config = load_model_config()
        assert "p3_scripting" in config["models"]

    def test_p3_model_is_claude_sonnet_4_6(self):
        """p3_scripting canonical model must be anthropic/claude-sonnet-4-6."""
        config = load_model_config()
        assert config["models"]["p3_scripting"] == "anthropic/claude-sonnet-4-6"

    def test_p1_model_string_present(self):
        """p1_research model must be defined (Phase 2 prep)."""
        config = load_model_config()
        assert "p1_research" in config["models"]

    def test_p1_model_is_deepseek(self):
        """p1_research must target DeepSeek V3 via OpenRouter."""
        config = load_model_config()
        assert config["models"]["p1_research"] == "deepseek/deepseek-chat"

    def test_fallback_model_present(self):
        """Fallback model must be defined in config."""
        config = load_model_config()
        assert "fallback" in config["models"]
        assert config["models"]["fallback"] == "anthropic/claude-haiku-4-5-20251001"


class TestFallbackMap:
    """Verify the fallback model map in llm_client matches config."""

    def test_p3_fallback_is_haiku(self):
        """P3 model must fall back to Haiku."""
        fb = OpenRouterLLMAdapter.FALLBACK_MODELS
        assert fb["anthropic/claude-sonnet-4-6"] == "anthropic/claude-haiku-4-5-20251001"

    def test_deepseek_fallback_is_haiku(self):
        """DeepSeek must fall back to Haiku."""
        fb = OpenRouterLLMAdapter.FALLBACK_MODELS
        assert fb["deepseek/deepseek-chat"] == "anthropic/claude-haiku-4-5-20251001"

    def test_fallback_map_has_exactly_two_entries(self):
        """Only ContentEngine roster models should have fallback entries."""
        fb = OpenRouterLLMAdapter.FALLBACK_MODELS
        assert len(fb) == 2


class TestLLMClientConfig:
    """Verify llm_client.py constructor and defaults."""

    def test_default_model_is_sonnet(self):
        """Factory default model must be anthropic/claude-sonnet-4-6."""
        # Can't instantiate without API key, but check class default
        import inspect
        sig = inspect.signature(OpenRouterLLMAdapter.__init__)
        default_model = sig.parameters["model"].default
        assert default_model == "anthropic/claude-sonnet-4-6"

    def test_cost_tracker_defaults_to_none(self):
        """cost_tracker must default to None (no global singleton)."""
        import inspect
        sig = inspect.signature(OpenRouterLLMAdapter.__init__)
        default_ct = sig.parameters["cost_tracker"].default
        assert default_ct is None

    def test_requires_api_key(self):
        """Constructor must raise LLMError when no API key is available."""
        # Temporarily clear the env var
        original = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
                OpenRouterLLMAdapter(api_key=None)
        finally:
            if original:
                os.environ["OPENROUTER_API_KEY"] = original


class TestHeaders:
    """FIX 5: Verify updated headers in _make_request."""

    def test_referer_is_content_engine(self):
        """HTTP-Referer must point to content-engine repo."""
        # Inspect source — this is a static check
        import inspect
        source = inspect.getsource(OpenRouterLLMAdapter._make_request)
        assert "rfd62794/content-engine" in source

    def test_x_title_is_content_engine(self):
        """X-Title must be ContentEngine."""
        import inspect
        source = inspect.getsource(OpenRouterLLMAdapter._make_request)
        assert '"ContentEngine"' in source


class TestResponseFormatDefault:
    """FIX 1: Verify generate() defaults to JSON mode."""

    def test_generate_signature_has_response_format(self):
        """generate() must accept response_format parameter."""
        import inspect
        sig = inspect.signature(OpenRouterLLMAdapter.generate)
        assert "response_format" in sig.parameters

    def test_response_format_default_is_none(self):
        """response_format default is None (resolved to json_object in body)."""
        import inspect
        sig = inspect.signature(OpenRouterLLMAdapter.generate)
        default = sig.parameters["response_format"].default
        # Default is None in signature, resolved to {"type": "json_object"} in body
        assert default is None


class TestUsageKeyBrittleness:
    """Audit finding: _validate_response must not hard-fail on missing usage."""

    def test_validate_response_accepts_missing_usage(self):
        """Response without 'usage' key should not raise LLMResponseError."""
        # Construct a minimal valid response WITHOUT usage
        response = {
            "choices": [
                {
                    "message": {
                        "content": '{"hook_short_script": "test"}',
                        "role": "assistant",
                    }
                }
            ]
        }
        # This should NOT raise — usage absence is handled gracefully
        adapter = OpenRouterLLMAdapter.__new__(OpenRouterLLMAdapter)
        adapter._validate_response(response)  # No exception = pass


# =============================================================================
# TIER 2: Live connection tests (skipped without API key)
# =============================================================================

requires_api_key = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set — skipping live connection test"
)


@requires_api_key
class TestLiveConnection:
    """Live ping to OpenRouter — validates real connectivity."""

    def test_ping_openrouter_with_p3_model(self):
        """Send a minimal prompt to p3_scripting model and verify JSON response."""
        config = load_model_config()
        model = config["models"]["p3_scripting"]

        client = OpenRouterLLMAdapter(model=model)
        result = client.generate(
            prompt="Respond with exactly this JSON: {\"status\": \"ok\"}",
            system_prompt="You are a test endpoint. Respond with valid JSON only.",
            max_tokens=50,
            temperature=0.0,
        )

        assert "text" in result
        assert result["text"] is not None

        # Verify response is valid JSON
        parsed = json.loads(result["text"])
        assert isinstance(parsed, dict)

    def test_ping_response_has_usage(self):
        """Live response should include usage data when available."""
        config = load_model_config()
        model = config["models"]["p3_scripting"]

        client = OpenRouterLLMAdapter(model=model)
        result = client.generate(
            prompt="Respond with: {\"test\": true}",
            system_prompt="Respond with valid JSON only.",
            max_tokens=50,
            temperature=0.0,
        )

        # Usage may be present — verify structure if so
        usage = result.get("usage", {})
        if usage:
            assert isinstance(usage, dict)

    def test_hook_key_present_with_script_prompt(self):
        """Full script prompt should produce response with hook_short_script key."""
        config = load_model_config()
        model = config["models"]["p3_scripting"]

        client = OpenRouterLLMAdapter(model=model)

        # Minimal script generation prompt
        result = client.generate(
            prompt=(
                'Write a YouTube script as JSON with keys: '
                '"hook_short_script" (100 words about idle game prestige loops), '
                '"mid_form_body" (450 words), '
                '"title_suggestion" (max 80 chars), '
                '"tags" (array of 6 strings). '
                'Respond with valid JSON only.'
            ),
            system_prompt=(
                "You are a YouTube script writer. Respond with a single "
                "valid JSON object. No markdown. No commentary."
            ),
            max_tokens=2048,
            temperature=0.7,
        )

        parsed = json.loads(result["text"])
        assert "hook_short_script" in parsed, f"Missing hook_short_script. Keys: {list(parsed.keys())}"

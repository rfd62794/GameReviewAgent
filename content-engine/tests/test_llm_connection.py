"""
ContentEngine LLM Connection Test

Verifies that:
1. models.yaml exists and parses correctly
2. Model string resolves to the expected value for each stage
3. ANTHROPIC_API_KEY is set (does NOT make an actual API call)
4. The anthropic SDK is importable

This test runs offline — no API calls. It validates configuration
readiness before any generation attempt.
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure content-engine root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.script_generator import (
    load_model_config,
    _resolve_model_string,
    MODELS_CONFIG_PATH,
)


class TestModelConfig:
    """Verify models.yaml is present and correctly structured."""

    def test_models_yaml_exists(self):
        """models.yaml must exist at project root."""
        assert MODELS_CONFIG_PATH.exists(), f"Missing: {MODELS_CONFIG_PATH}"

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

    def test_p3_resolves_to_direct_string(self):
        """For direct routing, model string must strip provider prefix."""
        config = load_model_config()
        resolved = _resolve_model_string(config, "p3_scripting")
        assert resolved == "claude-sonnet-4-6", f"Got: {resolved}"

    def test_p1_model_string_present(self):
        """p1_research model must be defined (Phase 2 prep)."""
        config = load_model_config()
        assert "p1_research" in config["models"]

    def test_p1_model_is_deepseek(self):
        """p1_research must target DeepSeek V3 via OpenRouter."""
        config = load_model_config()
        assert config["models"]["p1_research"] == "deepseek/deepseek-chat"


class TestAPIReadiness:
    """Verify SDK and env are configured (no actual API calls)."""

    def test_anthropic_sdk_importable(self):
        """anthropic Python SDK must be installed."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("anthropic SDK not installed — install before generation")

    def test_anthropic_api_key_set(self):
        """ANTHROPIC_API_KEY must be set in environment."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            pytest.skip(
                "ANTHROPIC_API_KEY not set — set before generation attempt"
            )
        # Sanity check: key should look like a real key (starts with sk-)
        assert key.startswith("sk-"), "ANTHROPIC_API_KEY doesn't start with 'sk-'"

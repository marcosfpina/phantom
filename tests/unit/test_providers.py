"""
Unit tests for the providers module.

Tests: ProviderConfig, GenerationResult, LlamaCppProvider (with mocked HTTP).
"""

from unittest.mock import MagicMock, patch

import pytest

from phantom.providers.base import (
    GenerationResult,
    ProviderConfig,
    ProviderStatus,
)
from phantom.providers.llamacpp import LlamaCppProvider

pytestmark = pytest.mark.unit


class TestProviderConfig:
    """Test ProviderConfig dataclass."""

    def test_defaults(self):
        cfg = ProviderConfig()
        assert cfg.base_url == ""
        assert cfg.api_key == ""
        assert cfg.timeout == 120
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.3
        assert cfg.max_retries == 3

    def test_custom_values(self):
        cfg = ProviderConfig(
            base_url="http://localhost:8080",
            model="llama-3",
            timeout=60,
            max_tokens=4096,
        )
        assert cfg.base_url == "http://localhost:8080"
        assert cfg.model == "llama-3"
        assert cfg.timeout == 60
        assert cfg.max_tokens == 4096


class TestGenerationResult:
    """Test GenerationResult dataclass."""

    def test_defaults(self):
        r = GenerationResult(text="hello")
        assert r.text == "hello"
        assert r.tokens_used == 0
        assert r.finish_reason == "stop"
        assert r.cached is False

    def test_custom_values(self):
        r = GenerationResult(
            text="output",
            tokens_used=42,
            model="llama-3-8b",
            finish_reason="length",
            latency_ms=150.0,
        )
        assert r.tokens_used == 42
        assert r.model == "llama-3-8b"
        assert r.latency_ms == 150.0


class TestLlamaCppProvider:
    """Test LlamaCppProvider initialization and methods."""

    def test_name(self):
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        assert provider.name == "llamacpp"

    def test_default_url_from_env(self):
        with patch.dict("os.environ", {"LLAMACPP_URL": "http://custom:9999"}):
            provider = LlamaCppProvider()
            assert provider.config.base_url == "http://custom:9999"

    def test_default_url_fallback(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = LlamaCppProvider()
            assert provider.config.base_url == LlamaCppProvider.DEFAULT_URL

    def test_initial_status_unavailable(self):
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        assert provider.status == ProviderStatus.UNAVAILABLE

    @patch("phantom.providers.llamacpp.requests.get")
    def test_is_available_success(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        assert provider.is_available() is True
        assert provider.status == ProviderStatus.AVAILABLE

    @patch("phantom.providers.llamacpp.requests.get")
    def test_is_available_failure(self, mock_get):
        mock_get.side_effect = ConnectionError("refused")
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        assert provider.is_available() is False
        assert provider.status == ProviderStatus.UNAVAILABLE

    @patch("phantom.providers.llamacpp.requests.get")
    def test_is_available_cached(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        provider.is_available()  # First call
        provider.is_available()  # Second call — should use cached result
        mock_get.assert_called_once()

    @patch("phantom.providers.llamacpp.requests.post")
    def test_generate_success(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "content": "Generated text",
                "tokens_evaluated": 10,
                "model": "llama-3",
                "stop_type": "stop",
            }),
        )
        mock_post.return_value.raise_for_status = MagicMock()

        provider = LlamaCppProvider(base_url="http://localhost:8080")
        result = provider.generate("Hello, world!")

        assert isinstance(result, GenerationResult)
        assert result.text == "Generated text"
        assert result.tokens_used == 10

    @patch("phantom.providers.llamacpp.requests.post")
    def test_generate_failure_raises(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("timeout")

        provider = LlamaCppProvider(base_url="http://localhost:8080")
        with pytest.raises(RuntimeError, match="Generation failed"):
            provider.generate("Hello")

    def test_repr(self):
        provider = LlamaCppProvider(base_url="http://localhost:8080")
        r = repr(provider)
        assert "llamacpp" in r
        assert "unavailable" in r

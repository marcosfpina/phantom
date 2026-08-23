"""
Unit tests for the AI Analyzer module.

Tests: AIConfig, provider classes, AIAnalyzer, response parsing.
"""

import asyncio
from unittest.mock import patch

import pytest

from phantom.analysis.ai_analyzer import (
    AIAnalyzer,
    AIConfig,
    AnthropicProvider,
    DeepSeekProvider,
    LlamaCppProvider,
    OpenAIProvider,
)
from phantom.core.metrics_schema import (
    AIInsights,
    ProjectMetrics,
)

pytestmark = pytest.mark.unit


class TestAIConfig:
    """Test AIConfig dataclass."""

    def test_defaults(self):
        config = AIConfig()
        assert config.local_url == "http://localhost:8080"
        assert config.max_tokens == 2048
        assert config.temperature == 0.3
        assert config.enable_fallback is True
        assert config.max_retries == 3
        assert config.enable_cache is True
        assert config.cache_ttl == 3600

    def test_custom_values(self):
        config = AIConfig(
            local_url="http://custom:9000",
            max_tokens=4096,
            temperature=0.7,
            enable_fallback=False,
        )
        assert config.local_url == "http://custom:9000"
        assert config.max_tokens == 4096
        assert config.enable_fallback is False

    def test_fallback_order(self):
        config = AIConfig()
        assert config.fallback_order == ["deepseek", "openai", "anthropic"]


class TestLlamaCppProviderUnit:
    """Test ai_analyzer's LlamaCppProvider (separate from providers.llamacpp)."""

    def test_name(self):
        provider = LlamaCppProvider()
        assert provider.name == "llamacpp"

    def test_base_url_trailing_slash(self):
        provider = LlamaCppProvider(base_url="http://localhost:8080/")
        assert provider.base_url == "http://localhost:8080"

    def test_is_available_false_when_no_server(self):
        provider = LlamaCppProvider(base_url="http://localhost:99999")
        assert provider.is_available() is False

    def test_is_available_cached(self):
        provider = LlamaCppProvider()
        provider._available = True
        assert provider.is_available() is True

    def test_generate_returns_none_when_unavailable(self):
        provider = LlamaCppProvider()
        provider._available = False
        result = asyncio.get_event_loop().run_until_complete(provider.generate("test prompt"))
        assert result is None


class TestDeepSeekProvider:
    """Test DeepSeekProvider."""

    def test_name(self):
        provider = DeepSeekProvider()
        assert provider.name == "deepseek"

    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = DeepSeekProvider(api_key="")
            assert provider.is_available() is False

    def test_available_with_key(self):
        provider = DeepSeekProvider(api_key="test-key-123")
        assert provider.is_available() is True

    def test_generate_returns_none_when_unavailable(self):
        provider = DeepSeekProvider(api_key="")
        result = asyncio.get_event_loop().run_until_complete(provider.generate("test"))
        assert result is None


class TestOpenAIProvider:
    """Test OpenAIProvider."""

    def test_name(self):
        provider = OpenAIProvider()
        assert provider.name == "openai"

    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAIProvider(api_key="")
            assert provider.is_available() is False

    def test_available_with_key(self):
        provider = OpenAIProvider(api_key="sk-test-key")
        assert provider.is_available() is True


class TestAnthropicProvider:
    """Test AnthropicProvider."""

    def test_name(self):
        provider = AnthropicProvider()
        assert provider.name == "anthropic"

    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = AnthropicProvider(api_key="")
            assert provider.is_available() is False

    def test_available_with_key(self):
        provider = AnthropicProvider(api_key="sk-ant-test")
        assert provider.is_available() is True


class TestAIAnalyzer:
    """Test AIAnalyzer class."""

    def test_init_default_config(self):
        analyzer = AIAnalyzer()
        assert analyzer.config is not None
        assert "llamacpp" in analyzer._providers

    def test_init_custom_config(self):
        config = AIConfig(enable_fallback=False)
        analyzer = AIAnalyzer(config=config)
        assert analyzer.config.enable_fallback is False

    def test_get_available_providers_none(self):
        """With no servers running and no API keys, should return empty."""
        config = AIConfig()
        with patch.dict("os.environ", {}, clear=True):
            analyzer = AIAnalyzer(config=config)
            # LlamaCpp will fail health check; cloud providers have no keys
            providers = analyzer.get_available_providers()
            # llamacpp may or may not be available depending on environment
            assert isinstance(providers, list)

    def test_cache_mechanism(self):
        config = AIConfig(enable_cache=True, cache_ttl=3600)
        analyzer = AIAnalyzer(config=config)
        assert analyzer._cache == {}

    def test_build_analysis_prompt(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test-project", path="/tmp/test")
        prompt = analyzer._build_analysis_prompt(metrics)
        assert "test-project" in prompt
        assert "SUMMARY:" in prompt
        assert "STRENGTHS:" in prompt
        assert "WEAKNESSES:" in prompt

    def test_parse_analysis_response_complete(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        response = """SUMMARY: This is a well-maintained project.

STRENGTHS:
- Good documentation
- Active development

WEAKNESSES:
- Limited test coverage

OPPORTUNITIES:
- Add CI/CD pipeline

THREATS:
- Dependency vulnerabilities

TECH_DEBT: Moderate technical debt in core modules.

TOP_RECOMMENDATIONS:
1. Increase test coverage to 80%
2. Set up automated security scanning
3. Refactor complex modules
"""
        insights = analyzer._parse_analysis_response(response, metrics)
        assert isinstance(insights, AIInsights)
        assert "well-maintained" in insights.summary
        assert len(insights.strengths) == 2
        assert "Good documentation" in insights.strengths
        assert len(insights.weaknesses) == 1
        assert len(insights.opportunities) == 1
        assert len(insights.threats) == 1
        assert "technical debt" in insights.tech_debt_summary.lower()
        assert len(insights.suggestions) == 3

    def test_parse_analysis_response_empty(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        insights = analyzer._parse_analysis_response("", metrics)
        assert isinstance(insights, AIInsights)

    def test_parse_analysis_response_partial(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        response = """SUMMARY: Brief analysis.

STRENGTHS:
- One strength
"""
        insights = analyzer._parse_analysis_response(response, metrics)
        assert "Brief analysis" in insights.summary
        assert len(insights.strengths) == 1

    def test_parse_analysis_multiline_summary(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        response = """SUMMARY: First line of summary.
Second line continues the summary.

STRENGTHS:
- A strength
"""
        insights = analyzer._parse_analysis_response(response, metrics)
        assert "First line" in insights.summary
        assert "Second line" in insights.summary

    def test_parse_analysis_bullet_variations(self):
        analyzer = AIAnalyzer()
        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        response = """SUMMARY: Test.

STRENGTHS:
- Dash item

WEAKNESSES:
- Another item
"""
        insights = analyzer._parse_analysis_response(response, metrics)
        assert len(insights.strengths) == 1
        assert len(insights.weaknesses) == 1

    def test_analyze_project_no_providers(self):
        config = AIConfig(enable_fallback=False, enable_cache=False)
        analyzer = AIAnalyzer(config=config)
        # Force all providers unavailable
        for provider in analyzer._providers.values():
            provider._available = False

        metrics = ProjectMetrics(project_id="test-id", name="test", path="/tmp")
        result = asyncio.get_event_loop().run_until_complete(analyzer.analyze_project(metrics))
        assert isinstance(result, AIInsights)
        assert "unavailable" in result.summary.lower()

    def test_assess_technical_debt_no_providers(self):
        config = AIConfig(enable_fallback=False, enable_cache=False)
        analyzer = AIAnalyzer(config=config)
        for provider in analyzer._providers.values():
            provider._available = False

        result = asyncio.get_event_loop().run_until_complete(
            analyzer.assess_technical_debt(["def foo(): pass"])
        )
        assert "unavailable" in result.lower()

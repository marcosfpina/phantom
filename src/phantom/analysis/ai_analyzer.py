#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PROJECTPHANTOM - AI ANALYZER                              ║
║              Unified AI Analysis Interface with Local-First Approach        ║
╚══════════════════════════════════════════════════════════════════════════════╝

AI-powered project analysis using:
- Local LlamaCpp server (primary)
- Cloud providers as fallback (DeepSeek, OpenAI, Anthropic)

Capabilities:
- Semantic code analysis
- Technical debt assessment
- Improvement suggestions
- Risk identification
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from phantom.core.metrics_schema import (
    AIInsights,
    ImprovementSuggestion,
    ProjectMetrics,
    RiskLevel,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AIConfig:
    """AI analyzer configuration."""

    # Local LlamaCpp
    local_url: str = "http://localhost:8080"
    local_model: str = "default"
    local_timeout: int = 120

    # Cloud providers
    enable_fallback: bool = True
    fallback_order: list[str] = field(
        default_factory=lambda: ["deepseek", "openai", "anthropic"]
    )

    # Generation parameters
    max_tokens: int = 2048
    temperature: float = 0.3
    top_p: float = 0.9

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 2.0

    # Cache settings
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hour


DEFAULT_CONFIG = AIConfig()


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER INTERFACE
# ══════════════════════════════════════════════════════════════════════════════


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 2048) -> str | None:
        pass


class LlamaCppProvider(AIProvider):
    """Local LlamaCpp server provider."""

    def __init__(self, base_url: str = "http://localhost:8081", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None

    @property
    def name(self) -> str:
        return "llamacpp"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available

        try:
            if REQUESTS_AVAILABLE:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                self._available = response.status_code == 200
            else:
                self._available = False
        except Exception:
            self._available = False

        logger.debug(f"LlamaCpp availability: {self._available}")
        return self._available

    async def generate(self, prompt: str, max_tokens: int = 2048) -> str | None:
        if not self.is_available():
            return None

        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": 0.3,
            "top_p": 0.9,
            "stop": ["</s>", "###"],
            "stream": False,
        }

        try:
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/completion", json=payload
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data.get("content", "")
            elif REQUESTS_AVAILABLE:
                response = requests.post(
                    f"{self.base_url}/completion", json=payload, timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("content", "")
        except Exception as e:
            logger.error(f"LlamaCpp generation failed: {e}")

        return None


class DeepSeekProvider(AIProvider):
    """DeepSeek API provider."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = "https://api.deepseek.com/v1"

    @property
    def name(self) -> str:
        return "deepseek"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 2048) -> str | None:
        if not self.is_available():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        try:
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data["choices"][0]["message"]["content"]
            elif REQUESTS_AVAILABLE:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek generation failed: {e}")

        return None


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = "https://api.openai.com/v1"

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 2048) -> str | None:
        if not self.is_available():
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        try:
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data["choices"][0]["message"]["content"]
            elif REQUESTS_AVAILABLE:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")

        return None


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 2048) -> str | None:
        if not self.is_available():
            return None

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        f"{self.base_url}/messages", json=payload, headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return data["content"][0]["text"]
            elif REQUESTS_AVAILABLE:
                response = requests.post(
                    f"{self.base_url}/messages",
                    json=payload,
                    headers=headers,
                    timeout=60,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data["content"][0]["text"]
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")

        return None


# ══════════════════════════════════════════════════════════════════════════════
# AI ANALYZER
# ══════════════════════════════════════════════════════════════════════════════


class AIAnalyzer:
    """Unified AI analysis interface with local-first approach."""

    def __init__(self, config: AIConfig | None = None):
        """
        Initialize AI analyzer.

        Args:
            config: AI configuration
        """
        self.config = config or DEFAULT_CONFIG
        self._providers: dict[str, AIProvider] = {}
        self._cache: dict[str, tuple[str, float]] = {}  # hash -> (response, timestamp)

        self._init_providers()

    def _init_providers(self) -> None:
        """Initialize all available providers."""
        # Local provider (always first priority)
        self._providers["llamacpp"] = LlamaCppProvider(
            self.config.local_url, self.config.local_timeout
        )

        # Cloud providers
        self._providers["deepseek"] = DeepSeekProvider()
        self._providers["openai"] = OpenAIProvider()
        self._providers["anthropic"] = AnthropicProvider()

        # Log availability
        for name, provider in self._providers.items():
            if provider.is_available():
                logger.info(f"AI Provider available: {name}")

    def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        return [name for name, p in self._providers.items() if p.is_available()]

    async def generate(self, prompt: str, prefer_local: bool = True) -> str | None:
        """
        Generate AI response with automatic fallback.

        Args:
            prompt: Input prompt
            prefer_local: Prefer local inference over cloud

        Returns:
            Generated response or None
        """
        # Check cache
        if self.config.enable_cache:
            cache_key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            if cache_key in self._cache:
                response, timestamp = self._cache[cache_key]
                if time.time() - timestamp < self.config.cache_ttl:
                    logger.debug(f"Cache hit for prompt: {cache_key}")
                    return response

        # Build provider order
        order = []
        if prefer_local:
            order.append("llamacpp")
        if self.config.enable_fallback:
            order.extend(self.config.fallback_order)
        if not prefer_local:
            order.append("llamacpp")

        # Try each provider in order
        for provider_name in order:
            provider = self._providers.get(provider_name)
            if not provider or not provider.is_available():
                continue

            logger.debug(f"Trying provider: {provider_name}")

            for attempt in range(self.config.max_retries):
                try:
                    response = await provider.generate(prompt, self.config.max_tokens)
                    if response:
                        # Cache successful response
                        if self.config.enable_cache:
                            self._cache[cache_key] = (response, time.time())

                        logger.info(f"Generated response using {provider_name}")
                        return response
                except Exception as e:
                    logger.warning(
                        f"Provider {provider_name} attempt {attempt + 1} failed: {e}"
                    )
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay)

        logger.error("All AI providers failed")
        return None

    async def analyze_project(self, metrics: ProjectMetrics) -> AIInsights:
        """
        Generate AI insights for a project.

        Args:
            metrics: Project metrics

        Returns:
            AI-generated insights
        """
        prompt = self._build_analysis_prompt(metrics)

        response = await self.generate(prompt)

        if not response:
            return AIInsights(
                summary="AI analysis unavailable - all providers failed",
                strengths=[],
                weaknesses=["AI analysis could not be completed"],
                opportunities=[],
                threats=[],
            )

        return self._parse_analysis_response(response, metrics)

    def _build_analysis_prompt(self, metrics: ProjectMetrics) -> str:
        """Build analysis prompt from metrics."""
        return f"""Analyze the following project and provide insights. Return a structured analysis.

PROJECT: {metrics.name}
PATH: {metrics.path}

CODE METRICS:
- Total lines: {metrics.code.total_lines}
- Languages: {", ".join(metrics.tech_stack.primary_languages)}
- Frameworks: {", ".join(metrics.tech_stack.frameworks)}
- File count: {metrics.code.file_count}

ACTIVITY:
- Days since last commit: {metrics.activity.days_since_last_commit}
- Commits last year: {metrics.activity.commits_last_year}
- Contributors: {metrics.activity.total_contributors}

QUALITY:
- Documentation score: {metrics.quality.documentation_score:.1f}/100
- Has README: {metrics.quality.readme_exists}
- Test coverage estimate: {metrics.quality.test_coverage_estimate:.1f}%
- Linting configured: {metrics.quality.linting_configured}

SECURITY:
- Security score: {metrics.security.security_score:.1f}/100
- Vulnerabilities: {metrics.security.vulnerabilities_critical} critical, \
{metrics.security.vulnerabilities_high} high
- Secrets detected: {metrics.security.secrets_detected}

DEPENDENCIES:
- Total: {metrics.dependencies.total_dependencies}
- Outdated: {metrics.dependencies.outdated_dependencies}

Provide your analysis in the following format:

SUMMARY: (one paragraph overview)

STRENGTHS:
- (strength 1)
- (strength 2)
- ...

WEAKNESSES:
- (weakness 1)
- (weakness 2)
- ...

OPPORTUNITIES:
- (opportunity 1)
- (opportunity 2)
- ...

THREATS:
- (threat 1)
- (threat 2)
- ...

TECH_DEBT: (brief assessment)

TOP_RECOMMENDATIONS:
1. (recommendation 1)
2. (recommendation 2)
3. (recommendation 3)
"""

    def _parse_analysis_response(
        self, response: str, metrics: ProjectMetrics
    ) -> AIInsights:
        """Parse AI response into structured insights."""
        insights = AIInsights()

        try:
            lines = response.strip().split("\n")
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Detect section headers
                if line.startswith("SUMMARY:"):
                    insights.summary = line.replace("SUMMARY:", "").strip()
                    current_section = "summary"
                elif line.startswith("STRENGTHS:"):
                    current_section = "strengths"
                elif line.startswith("WEAKNESSES:"):
                    current_section = "weaknesses"
                elif line.startswith("OPPORTUNITIES:"):
                    current_section = "opportunities"
                elif line.startswith("THREATS:"):
                    current_section = "threats"
                elif line.startswith("TECH_DEBT:"):
                    insights.tech_debt_summary = line.replace("TECH_DEBT:", "").strip()
                    current_section = "tech_debt"
                elif line.startswith("TOP_RECOMMENDATIONS:"):
                    current_section = "recommendations"
                elif line.startswith("- ") or line.startswith("• "):
                    item = line[2:].strip()
                    if current_section == "strengths":
                        insights.strengths.append(item)
                    elif current_section == "weaknesses":
                        insights.weaknesses.append(item)
                    elif current_section == "opportunities":
                        insights.opportunities.append(item)
                    elif current_section == "threats":
                        insights.threats.append(item)
                elif line[0].isdigit() and "." in line:
                    # Numbered recommendation
                    if current_section == "recommendations":
                        rec_text = (
                            line.split(".", 1)[1].strip() if "." in line else line
                        )
                        insights.suggestions.append(
                            ImprovementSuggestion(
                                title=rec_text[:50],
                                description=rec_text,
                                priority=RiskLevel.MEDIUM,
                                category="ai_recommendation",
                            )
                        )
                elif current_section == "summary" and not line.startswith(
                    ("STRENGTHS", "WEAKNESSES")
                ):
                    # Continue summary on next lines
                    if insights.summary:
                        insights.summary += " " + line
                    else:
                        insights.summary = line
                elif current_section == "tech_debt" and not line.startswith("TOP_"):
                    insights.tech_debt_summary += " " + line

        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            insights.summary = (
                f"Analysis generated but parsing failed: {response[:200]}..."
            )

        return insights

    async def assess_technical_debt(self, code_samples: list[str]) -> str:
        """
        AI-powered technical debt assessment.

        Args:
            code_samples: List of code snippets to analyze

        Returns:
            Technical debt assessment summary
        """
        prompt = f"""Analyze the following code samples for technical debt indicators.
Identify:
1. Code smells
2. Anti-patterns
3. Maintainability issues
4. Suggested refactoring

CODE SAMPLES:
{chr(10).join(f"```{sample}```" for sample in code_samples[:5])}

Provide a brief, actionable assessment focusing on the most critical issues.
"""

        response = await self.generate(prompt)
        return response or "Technical debt assessment unavailable"

    async def suggest_improvements(
        self, metrics: ProjectMetrics
    ) -> list[ImprovementSuggestion]:
        """
        Generate prioritized improvement suggestions.

        Args:
            metrics: Project metrics

        Returns:
            List of improvement suggestions
        """
        prompt = f"""Based on the following project metrics, provide 5 specific, actionable \
improvement suggestions.
Prioritize by impact and effort.

PROJECT: {metrics.name}
- Code quality: {metrics.quality.documentation_score}/100
- Security: {metrics.security.security_score}/100
- Activity: {metrics.activity.commits_last_30_days} commits/month
- Test coverage: ~{metrics.quality.test_coverage_estimate}%
- Tech stack: {", ".join(metrics.tech_stack.primary_languages)}

For each suggestion, provide:
- Title (brief)
- Description (specific actions)
- Priority (low/medium/high)
- Effort (low/medium/high)

Format as:
1. [PRIORITY/EFFORT] Title: Description
2. ...
"""

        response = await self.generate(prompt)

        suggestions = []
        if response:
            lines = response.strip().split("\n")
            for line in lines:
                if line and line[0].isdigit():
                    try:
                        # Parse format: 1. [HIGH/LOW] Title: Description
                        parts = line.split("]", 1)
                        if len(parts) == 2:
                            priority_effort = parts[0].split("[")[1].split("/")
                            priority = priority_effort[0].lower().strip()
                            effort = (
                                priority_effort[1].lower().strip()
                                if len(priority_effort) > 1
                                else "medium"
                            )

                            title_desc = parts[1].strip()
                            if ":" in title_desc:
                                title, desc = title_desc.split(":", 1)
                            else:
                                title = title_desc[:50]
                                desc = title_desc

                            priority_map = {
                                "low": RiskLevel.LOW,
                                "medium": RiskLevel.MEDIUM,
                                "high": RiskLevel.HIGH,
                            }

                            suggestions.append(
                                ImprovementSuggestion(
                                    title=title.strip(),
                                    description=desc.strip(),
                                    priority=priority_map.get(
                                        priority, RiskLevel.MEDIUM
                                    ),
                                    effort_estimate=effort,
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Error parsing suggestion: {e}")

        return suggestions


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


async def quick_analysis(metrics: ProjectMetrics) -> AIInsights:
    """
    Quick AI analysis of a project.

    Args:
        metrics: Project metrics

    Returns:
        AI insights
    """
    analyzer = AIAnalyzer()
    return await analyzer.analyze_project(metrics)


def sync_analysis(metrics: ProjectMetrics) -> AIInsights:
    """
    Synchronous wrapper for AI analysis.

    Args:
        metrics: Project metrics

    Returns:
        AI insights
    """
    return asyncio.run(quick_analysis(metrics))


async def check_providers() -> dict[str, bool]:
    """
    Check which AI providers are available.

    Returns:
        Dictionary of provider name to availability
    """
    analyzer = AIAnalyzer()
    return {
        name: provider.is_available() for name, provider in analyzer._providers.items()
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    async def main():
        print("AI Analyzer - Provider Check")
        print("=" * 40)

        analyzer = AIAnalyzer()
        providers = analyzer.get_available_providers()

        if not providers:
            print("❌ No AI providers available!")
            print("\nTo enable providers:")
            print("  - Local: Start LlamaCpp server on http://localhost:8081")
            print(
                "  - Cloud: Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
            )
            return

        print("Available providers:")
        for p in providers:
            print(f"  ✅ {p}")

        # Quick test
        print("\nTesting generation...")
        response = await analyzer.generate(
            "Say 'Hello from ProjectPhantom!' in one line."
        )
        if response:
            print(f"✅ Response: {response[:100]}")
        else:
            print("❌ Generation failed")

    asyncio.run(main())

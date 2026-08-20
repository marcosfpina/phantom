#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PROJECTPHANTOM - VIABILITY SCORER                         ║
║              Enterprise Project Viability Assessment System                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

ML-enhanced project viability scoring with configurable weights.
Provides enterprise-level project assessment and recommendations.
"""

import logging
from dataclasses import dataclass
from typing import Any

from phantom.core.metrics_schema import (
    ImprovementSuggestion,
    ProjectMetrics,
    RiskFactor,
    RiskLevel,
    ScoreBreakdown,
    ViabilityScore,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SCORING CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ScoringWeights:
    """Configurable scoring weights for viability assessment."""

    activity: float = 0.25  # Git activity, contributor engagement
    quality: float = 0.20  # Code quality, documentation
    complexity: float = 0.15  # Manageable complexity (inverted)
    security: float = 0.15  # Security posture
    maintenance: float = 0.15  # Technical debt, freshness
    potential: float = 0.10  # AI-assessed future potential

    def validate(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.activity
            + self.quality
            + self.complexity
            + self.security
            + self.maintenance
            + self.potential
        )
        return abs(total - 1.0) < 0.01


# Default weights
DEFAULT_WEIGHTS = ScoringWeights()

# Industry-specific weight presets
WEIGHT_PRESETS = {
    "default": ScoringWeights(),
    "security_focused": ScoringWeights(
        activity=0.15,
        quality=0.15,
        complexity=0.10,
        security=0.35,
        maintenance=0.15,
        potential=0.10,
    ),
    "startup": ScoringWeights(
        activity=0.20,
        quality=0.15,
        complexity=0.10,
        security=0.10,
        maintenance=0.15,
        potential=0.30,
    ),
    "enterprise": ScoringWeights(
        activity=0.20,
        quality=0.25,
        complexity=0.15,
        security=0.20,
        maintenance=0.15,
        potential=0.05,
    ),
    "maintenance_mode": ScoringWeights(
        activity=0.10,
        quality=0.20,
        complexity=0.20,
        security=0.20,
        maintenance=0.25,
        potential=0.05,
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# SCORING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


class ViabilityScorer:
    """Enterprise-level project viability scoring system."""

    def __init__(self, weights: ScoringWeights | None = None, preset: str = "default"):
        """
        Initialize scorer with weights.

        Args:
            weights: Custom scoring weights
            preset: Named preset ("default", "security_focused", "startup", "enterprise")
        """
        if weights:
            self.weights = weights
        else:
            self.weights = WEIGHT_PRESETS.get(preset, DEFAULT_WEIGHTS)

        if not self.weights.validate():
            logger.warning("Scoring weights do not sum to 1.0, normalizing...")
            self._normalize_weights()

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = (
            self.weights.activity
            + self.weights.quality
            + self.weights.complexity
            + self.weights.security
            + self.weights.maintenance
            + self.weights.potential
        )
        if total > 0:
            self.weights.activity /= total
            self.weights.quality /= total
            self.weights.complexity /= total
            self.weights.security /= total
            self.weights.maintenance /= total
            self.weights.potential /= total

    def calculate_score(self, metrics: ProjectMetrics) -> ViabilityScore:
        """
        Calculate comprehensive viability score with detailed breakdown.

        Args:
            metrics: Complete project metrics

        Returns:
            ViabilityScore with breakdown and recommendation
        """
        breakdown = ScoreBreakdown(
            activity_score=self._score_activity(metrics),
            activity_weight=self.weights.activity,
            quality_score=self._score_quality(metrics),
            quality_weight=self.weights.quality,
            complexity_score=self._score_complexity(metrics),
            complexity_weight=self.weights.complexity,
            security_score=self._score_security(metrics),
            security_weight=self.weights.security,
            maintenance_score=self._score_maintenance(metrics),
            maintenance_weight=self.weights.maintenance,
            potential_score=self._score_potential(metrics),
            potential_weight=self.weights.potential,
        )

        final_score = breakdown.weighted_total
        result = ViabilityScore.from_score(final_score, breakdown)

        logger.info(
            f"Project {metrics.name}: Viability Score = {final_score:.1f} ({result.grade})"
        )

        return result

    def _score_activity(self, metrics: ProjectMetrics) -> float:
        """
        Score project activity and engagement (0-100).

        Factors:
        - Recency of commits
        - Commit frequency
        - Contributor count
        - Commit velocity trends
        """
        score = 50.0  # Base score
        activity = metrics.activity

        if not activity.is_git_repo:
            return 20.0  # Non-git repos get low activity score

        # Recency bonus/penalty (max ±30)
        days = activity.days_since_last_commit
        if days <= 7:
            score += 30
        elif days <= 30:
            score += 20
        elif days <= 90:
            score += 10
        elif days <= 180:
            score -= 5
        elif days <= 365:
            score -= 15
        else:
            score -= 30

        # Commit frequency (max +15)
        commits_30d = activity.commits_last_30_days
        if commits_30d >= 50:
            score += 15
        elif commits_30d >= 20:
            score += 10
        elif commits_30d >= 10:
            score += 7
        elif commits_30d >= 5:
            score += 5
        elif commits_30d >= 1:
            score += 2

        # Contributor engagement (max +10)
        contributors = activity.active_contributors_30d
        if contributors >= 5:
            score += 10
        elif contributors >= 3:
            score += 7
        elif contributors >= 2:
            score += 5
        elif contributors >= 1:
            score += 2

        return max(0, min(100, score))

    def _score_quality(self, metrics: ProjectMetrics) -> float:
        """
        Score code quality (0-100).

        Factors:
        - Documentation coverage
        - README quality
        - Test coverage
        - Code organization
        - Linting/type checking
        """
        score = 50.0
        quality = metrics.quality

        # Documentation (max +20)
        if quality.readme_exists:
            score += 5
            score += quality.readme_quality * 0.1  # Up to +10 from quality
        if quality.has_changelog:
            score += 3
        if quality.has_contributing:
            score += 2
        if quality.has_license:
            score += 2

        # Testing (max +15)
        if quality.test_coverage_estimate > 80:
            score += 15
        elif quality.test_coverage_estimate > 60:
            score += 12
        elif quality.test_coverage_estimate > 40:
            score += 8
        elif quality.test_coverage_estimate > 20:
            score += 4
        elif quality.test_file_ratio > 0:
            score += 2

        # Tooling (max +10)
        if quality.linting_configured:
            score += 5
        if quality.type_checking_configured:
            score += 5

        # Duplication penalty (max -10)
        if quality.code_duplication_ratio > 30:
            score -= 10
        elif quality.code_duplication_ratio > 20:
            score -= 7
        elif quality.code_duplication_ratio > 10:
            score -= 4

        return max(0, min(100, score))

    def _score_complexity(self, metrics: ProjectMetrics) -> float:
        """
        Score manageable complexity (0-100).
        Higher score = more manageable complexity.

        Factors:
        - Cyclomatic complexity
        - Cognitive complexity
        - Maintainability index
        - Function/file sizes
        """
        score = 70.0  # Start optimistic
        complexity = metrics.complexity

        # Cyclomatic complexity penalty
        cc_avg = complexity.cyclomatic_complexity_avg
        if cc_avg > 15:
            score -= 25
        elif cc_avg > 10:
            score -= 15
        elif cc_avg > 7:
            score -= 8
        elif cc_avg > 5:
            score -= 3

        # Max complexity hotspots
        if complexity.cyclomatic_complexity_max > 50:
            score -= 15
        elif complexity.cyclomatic_complexity_max > 30:
            score -= 10
        elif complexity.cyclomatic_complexity_max > 20:
            score -= 5

        # Maintainability index bonus
        mi = complexity.maintainability_index
        if mi > 80:
            score += 20
        elif mi > 60:
            score += 15
        elif mi > 40:
            score += 10
        elif mi > 20:
            score -= 5
        else:
            score -= 15

        # File size penalty
        if metrics.code.avg_file_size > 500:
            score -= 10
        elif metrics.code.avg_file_size > 300:
            score -= 5

        # Function length penalty
        if complexity.avg_function_length > 50:
            score -= 10
        elif complexity.avg_function_length > 30:
            score -= 5

        return max(0, min(100, score))

    def _score_security(self, metrics: ProjectMetrics) -> float:
        """
        Score security posture (0-100).

        Factors:
        - Known vulnerabilities
        - Dependency security
        - Security tooling
        - Secrets detection
        """
        score = 100.0  # Start at perfect, deduct for issues
        security = metrics.security
        deps = metrics.dependencies

        # Critical vulnerabilities (severe penalty)
        score -= security.vulnerabilities_critical * 25
        score -= security.vulnerabilities_high * 10
        score -= security.vulnerabilities_medium * 3
        score -= security.vulnerabilities_low * 1

        # Secrets in code
        if security.secrets_detected > 0:
            score -= min(30, security.secrets_detected * 10)

        # Dependency security
        score -= deps.vulnerable_dependencies * 5

        # Security practices bonus
        if security.has_security_policy:
            score += 5
        if security.has_dependabot:
            score += 5
        if security.has_code_scanning:
            score += 5

        return max(0, min(100, score))

    def _score_maintenance(self, metrics: ProjectMetrics) -> float:
        """
        Score maintenance health (0-100).

        Factors:
        - Dependency freshness
        - Technical debt indicators
        - Outdated dependencies
        - Build system health
        """
        score = 70.0
        deps = metrics.dependencies

        # Dependency freshness
        freshness = deps.dependency_freshness
        if freshness > 80:
            score += 20
        elif freshness > 60:
            score += 10
        elif freshness > 40:
            score += 5
        elif freshness < 20:
            score -= 15

        # Outdated dependencies penalty
        outdated_ratio = deps.outdated_dependencies / max(1, deps.total_dependencies)
        if outdated_ratio > 0.5:
            score -= 20
        elif outdated_ratio > 0.3:
            score -= 10
        elif outdated_ratio > 0.1:
            score -= 5

        # Tech stack modernity
        modernity = metrics.tech_stack.stack_modernity_score
        if modernity > 80:
            score += 10
        elif modernity > 60:
            score += 5
        elif modernity < 30:
            score -= 10

        return max(0, min(100, score))

    def _score_potential(self, metrics: ProjectMetrics) -> float:
        """
        Score future potential (0-100).

        Factors:
        - Hot topic alignment
        - Tech stack trend
        - AI insights (if available)
        - Market positioning
        """
        score = 50.0

        # Hot topics bonus
        hot_topics = {
            "rust",
            "nix",
            "nixos",
            "ai",
            "llm",
            "agent",
            "ml",
            "wasm",
            "security",
            "encryption",
            "tauri",
            "svelte",
            "react",
            "nextjs",
            "kubernetes",
            "docker",
            "typescript",
            "go",
            "python",
        }

        all_tech = set()
        all_tech.update(t.lower() for t in metrics.tech_stack.primary_languages)
        all_tech.update(t.lower() for t in metrics.tech_stack.frameworks)

        matches = len(all_tech & hot_topics)
        score += min(25, matches * 5)

        # Stack modernity
        if metrics.tech_stack.stack_modernity_score > 70:
            score += 15
        elif metrics.tech_stack.stack_modernity_score > 50:
            score += 10

        # AI insights (if available)
        if metrics.ai_insights:
            # Positive factors
            score += len(metrics.ai_insights.strengths) * 2
            score += len(metrics.ai_insights.opportunities) * 3
            # Negative factors
            score -= len(metrics.ai_insights.weaknesses) * 1
            score -= len(metrics.ai_insights.threats) * 2

        return max(0, min(100, score))

    def generate_recommendation(
        self, score: ViabilityScore, metrics: ProjectMetrics
    ) -> str:
        """
        Generate actionable investment recommendation.

        Args:
            score: Calculated viability score
            metrics: Project metrics

        Returns:
            Detailed recommendation text
        """
        breakdown = score.breakdown
        project_name = metrics.name

        parts = [f"# Investment Recommendation: {project_name}"]
        parts.append(f"\n**Overall Score: {score.score:.1f}/100 ({score.grade})**")
        parts.append(f"\n**Recommendation: {score.recommendation_text}**\n")

        # Score breakdown
        parts.append("## Score Breakdown\n")
        parts.append(
            f"- Activity: {breakdown.activity_score:.1f}/100 "
            f"(weight: {breakdown.activity_weight:.0%})"
        )
        parts.append(
            f"- Quality: {breakdown.quality_score:.1f}/100 "
            f"(weight: {breakdown.quality_weight:.0%})"
        )
        parts.append(
            f"- Complexity: {breakdown.complexity_score:.1f}/100 "
            f"(weight: {breakdown.complexity_weight:.0%})"
        )
        parts.append(
            f"- Security: {breakdown.security_score:.1f}/100 "
            f"(weight: {breakdown.security_weight:.0%})"
        )
        parts.append(
            f"- Maintenance: {breakdown.maintenance_score:.1f}/100 "
            f"(weight: {breakdown.maintenance_weight:.0%})"
        )
        parts.append(
            f"- Potential: {breakdown.potential_score:.1f}/100 "
            f"(weight: {breakdown.potential_weight:.0%})"
        )

        # Key insights
        parts.append("\n## Key Insights\n")

        # Strengths
        strengths = []
        if breakdown.activity_score >= 70:
            strengths.append("Active development with regular commits")
        if breakdown.quality_score >= 70:
            strengths.append("Good code quality and documentation")
        if breakdown.security_score >= 80:
            strengths.append("Strong security posture")
        if breakdown.potential_score >= 70:
            strengths.append("Good alignment with trending technologies")

        if strengths:
            parts.append("**Strengths:**")
            for s in strengths:
                parts.append(f"  - {s}")

        # Weaknesses
        weaknesses = []
        if breakdown.activity_score < 40:
            weaknesses.append(
                f"Low activity ({metrics.activity.days_since_last_commit} days since last commit)"
            )
        if breakdown.quality_score < 40:
            weaknesses.append("Documentation and testing need improvement")
        if breakdown.security_score < 50:
            weaknesses.append(
                f"Security concerns ({metrics.security.vulnerabilities_critical} critical vulns)"
            )
        if breakdown.complexity_score < 40:
            weaknesses.append("High complexity may impede maintenance")
        if breakdown.maintenance_score < 40:
            weaknesses.append("Technical debt and outdated dependencies")

        if weaknesses:
            parts.append("\n**Areas for Improvement:**")
            for w in weaknesses:
                parts.append(f"  - {w}")

        # Action items
        parts.append("\n## Recommended Actions\n")

        actions = self._generate_actions(score, metrics)
        for i, action in enumerate(actions[:5], 1):
            parts.append(f"{i}. {action}")

        return "\n".join(parts)

    def _generate_actions(
        self, score: ViabilityScore, metrics: ProjectMetrics
    ) -> list[str]:
        """Generate prioritized action items."""
        actions = []
        breakdown = score.breakdown

        # Security is always priority if low
        if breakdown.security_score < 60:
            if metrics.security.vulnerabilities_critical > 0:
                actions.append(
                    "**URGENT**: Address critical security vulnerabilities immediately"
                )
            if metrics.security.secrets_detected > 0:
                actions.append(
                    "**URGENT**: Remove hardcoded secrets and rotate credentials"
                )
            if metrics.dependencies.vulnerable_dependencies > 0:
                actions.append("Update dependencies with known vulnerabilities")

        # Activity
        if breakdown.activity_score < 50:
            if metrics.activity.days_since_last_commit > 180:
                actions.append(
                    "Evaluate if project is still needed; consider archiving if not"
                )
            else:
                actions.append(
                    "Increase development cadence or define maintenance schedule"
                )

        # Quality
        if breakdown.quality_score < 50:
            if not metrics.quality.readme_exists:
                actions.append("Create comprehensive README documentation")
            if metrics.quality.test_coverage_estimate < 30:
                actions.append("Increase test coverage (target: 60%+)")
            if not metrics.quality.linting_configured:
                actions.append("Set up linting and code formatting")

        # Complexity
        if breakdown.complexity_score < 50:
            actions.append("Refactor high-complexity modules (CC > 10)")
            if metrics.code.avg_file_size > 300:
                actions.append("Split large files into smaller, focused modules")

        # Maintenance
        if breakdown.maintenance_score < 50 and metrics.dependencies.outdated_dependencies > 5:
            actions.append("Update outdated dependencies")

        # Potential
        if breakdown.potential_score < 50:
            actions.append(
                "Consider modernizing tech stack for better future maintainability"
            )

        # Default if no specific issues
        if not actions:
            actions.append("Continue current development practices")
            actions.append("Monitor for security updates")

        return actions

    def generate_risk_factors(self, metrics: ProjectMetrics) -> list[RiskFactor]:
        """
        Identify and score risk factors.

        Args:
            metrics: Project metrics

        Returns:
            List of identified risk factors
        """
        risks = []

        # Security risks
        if metrics.security.vulnerabilities_critical > 0:
            risks.append(
                RiskFactor(
                    category="Security",
                    description=(
                        f"{metrics.security.vulnerabilities_critical} critical vulnerabilities"
                    ),
                    severity=RiskLevel.CRITICAL,
                    impact="Potential security breach or exploitation",
                    mitigation="Immediately update affected dependencies",
                    score_impact=-15.0,
                )
            )

        if metrics.security.secrets_detected > 0:
            risks.append(
                RiskFactor(
                    category="Security",
                    description=(
                        f"Detected {metrics.security.secrets_detected} "
                        "potential secrets in code"
                    ),
                    severity=RiskLevel.HIGH,
                    impact="Credential exposure risk",
                    mitigation="Remove secrets, use environment variables or secrets manager",
                    score_impact=-10.0,
                )
            )

        # Activity risks
        if metrics.activity.days_since_last_commit > 365:
            risks.append(
                RiskFactor(
                    category="Maintenance",
                    description=f"No activity for {metrics.activity.days_since_last_commit} days",
                    severity=RiskLevel.HIGH,
                    impact="Project may be abandoned or unmaintainable",
                    mitigation="Assess project necessity; archive or revive",
                    score_impact=-20.0,
                )
            )

        # Dependency risks
        outdated_ratio = metrics.dependencies.outdated_dependencies / max(
            1, metrics.dependencies.total_dependencies
        )
        if outdated_ratio > 0.5:
            risks.append(
                RiskFactor(
                    category="Dependencies",
                    description="Over 50% of dependencies are outdated",
                    severity=RiskLevel.MEDIUM,
                    impact="Missing security patches and features",
                    mitigation="Schedule dependency update sprint",
                    score_impact=-10.0,
                )
            )

        # Complexity risks
        if metrics.complexity.cyclomatic_complexity_max > 50:
            risks.append(
                RiskFactor(
                    category="Complexity",
                    description=(
                        "Extremely complex code "
                        f"(CC max: {metrics.complexity.cyclomatic_complexity_max})"
                    ),
                    severity=RiskLevel.MEDIUM,
                    impact="High bug risk and maintenance burden",
                    mitigation="Refactor complex functions; add comprehensive tests",
                    score_impact=-8.0,
                )
            )

        # Single point of failure (single contributor)
        if metrics.activity.total_contributors == 1:
            risks.append(
                RiskFactor(
                    category="Bus Factor",
                    description="Single contributor project",
                    severity=RiskLevel.MEDIUM,
                    impact="Knowledge concentration; project at risk if contributor leaves",
                    mitigation="Document architecture; onboard additional contributors",
                    score_impact=-5.0,
                )
            )

        return risks

    def generate_suggestions(
        self, metrics: ProjectMetrics
    ) -> list[ImprovementSuggestion]:
        """
        Generate prioritized improvement suggestions.

        Args:
            metrics: Project metrics

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Documentation suggestions
        if not metrics.quality.readme_exists:
            suggestions.append(
                ImprovementSuggestion(
                    title="Create README",
                    description=(
                        "Add a comprehensive README with installation, usage, "
                        "and contribution guidelines"
                    ),
                    priority=RiskLevel.HIGH,
                    category="documentation",
                    effort_estimate="low",
                    expected_impact="Improved onboarding and discoverability",
                    related_metrics=["quality_score", "documentation_score"],
                )
            )

        # Testing suggestions
        if metrics.quality.test_coverage_estimate < 40:
            suggestions.append(
                ImprovementSuggestion(
                    title="Increase Test Coverage",
                    description=(
                        f"Current estimated coverage is "
                        f"{metrics.quality.test_coverage_estimate:.0f}%. Target 60%+"
                    ),
                    priority=RiskLevel.MEDIUM,
                    category="testing",
                    effort_estimate="medium",
                    expected_impact="Reduced bug rate and safer refactoring",
                    related_metrics=["quality_score", "complexity_score"],
                )
            )

        # Security suggestions
        if not metrics.security.has_dependabot:
            suggestions.append(
                ImprovementSuggestion(
                    title="Enable Dependabot",
                    description="Set up Dependabot or similar for automatic dependency updates",
                    priority=RiskLevel.MEDIUM,
                    category="security",
                    effort_estimate="low",
                    expected_impact="Automated security patch delivery",
                    related_metrics=["security_score", "maintenance_score"],
                )
            )

        # CI/CD suggestions
        if not metrics.quality.linting_configured:
            suggestions.append(
                ImprovementSuggestion(
                    title="Set Up CI/CD Pipeline",
                    description="Implement automated linting, testing, and build verification",
                    priority=RiskLevel.MEDIUM,
                    category="automation",
                    effort_estimate="medium",
                    expected_impact="Consistent code quality and faster iteration",
                    related_metrics=["quality_score"],
                )
            )

        # Modernization suggestions
        if metrics.tech_stack.stack_modernity_score < 40:
            suggestions.append(
                ImprovementSuggestion(
                    title="Tech Stack Modernization",
                    description="Consider updating to more recent framework/language versions",
                    priority=RiskLevel.LOW,
                    category="modernization",
                    effort_estimate="high",
                    expected_impact="Better performance, security, and developer experience",
                    related_metrics=["potential_score", "maintenance_score"],
                )
            )

        return suggestions


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


def quick_score(metrics: ProjectMetrics, preset: str = "default") -> float:
    """
    Quick viability score calculation.

    Args:
        metrics: Project metrics
        preset: Weight preset name

    Returns:
        Viability score (0-100)
    """
    scorer = ViabilityScorer(preset=preset)
    return scorer.calculate_score(metrics).score


def full_assessment(metrics: ProjectMetrics, preset: str = "default") -> dict[str, Any]:
    """
    Complete viability assessment with all details.

    Args:
        metrics: Project metrics
        preset: Weight preset name

    Returns:
        Complete assessment dictionary
    """
    scorer = ViabilityScorer(preset=preset)
    score = scorer.calculate_score(metrics)

    return {
        "project": metrics.name,
        "score": score.score,
        "grade": score.grade,
        "recommendation": score.recommendation.value,
        "breakdown": score.breakdown.model_dump(),
        "recommendation_text": scorer.generate_recommendation(score, metrics),
        "risk_factors": [r.model_dump() for r in scorer.generate_risk_factors(metrics)],
        "suggestions": [s.model_dump() for s in scorer.generate_suggestions(metrics)],
    }

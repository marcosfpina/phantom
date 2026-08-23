"""
Unit tests for the viability scorer module.

Tests: ScoringWeights, ViabilityScorer scoring methods, presets.
"""

import pytest

from phantom.analysis.viability_scorer import (
    DEFAULT_WEIGHTS,
    WEIGHT_PRESETS,
    ScoringWeights,
    ViabilityScorer,
)
from phantom.core.metrics_schema import (
    ActivityMetrics,
    CodeMetrics,
    ComplexityMetrics,
    DependencyMetrics,
    ProjectMetrics,
    QualityMetrics,
    SecurityMetrics,
    TechStackMetrics,
)

pytestmark = pytest.mark.unit


def _make_metrics(**overrides) -> ProjectMetrics:
    """Helper to build ProjectMetrics with sensible defaults."""
    return ProjectMetrics(
        project_id="test",
        name="TestProject",
        path="/tmp/test",
        **overrides,
    )


class TestScoringWeights:
    """Test weight configuration and validation."""

    def test_default_weights_sum_to_1(self):
        assert DEFAULT_WEIGHTS.validate()

    def test_all_presets_sum_to_1(self):
        for name, weights in WEIGHT_PRESETS.items():
            assert weights.validate(), f"Preset '{name}' weights don't sum to 1.0"

    def test_custom_weights_validation_pass(self):
        w = ScoringWeights(
            activity=0.30, quality=0.20, complexity=0.15,
            security=0.15, maintenance=0.10, potential=0.10,
        )
        assert w.validate()

    def test_custom_weights_validation_fail(self):
        w = ScoringWeights(
            activity=0.50, quality=0.50, complexity=0.50,
            security=0.50, maintenance=0.50, potential=0.50,
        )
        assert not w.validate()

    def test_presets_exist(self):
        assert "default" in WEIGHT_PRESETS
        assert "security_focused" in WEIGHT_PRESETS
        assert "startup" in WEIGHT_PRESETS
        assert "enterprise" in WEIGHT_PRESETS
        assert "maintenance_mode" in WEIGHT_PRESETS


class TestViabilityScorer:
    """Test the scorer's individual scoring methods."""

    def test_init_default_preset(self):
        scorer = ViabilityScorer()
        assert scorer.weights.validate()

    def test_init_security_preset(self):
        scorer = ViabilityScorer(preset="security_focused")
        assert scorer.weights.security == 0.35

    def test_normalizes_bad_weights(self):
        bad_weights = ScoringWeights(
            activity=0.5, quality=0.5, complexity=0.5,
            security=0.5, maintenance=0.5, potential=0.5,
        )
        scorer = ViabilityScorer(weights=bad_weights)
        # After normalization, weights should sum to 1.0
        assert scorer.weights.validate()

    def test_score_activity_git_repo(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(
                is_git_repo=True,
                days_since_last_commit=5,
                commits_last_30_days=25,
                active_contributors_30d=3,
            ),
        )
        score = scorer._score_activity(metrics)
        assert 0 <= score <= 100
        # Active repo with recent commits should score well
        assert score >= 70

    def test_score_activity_non_git(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(is_git_repo=False),
        )
        score = scorer._score_activity(metrics)
        assert score == 20.0

    def test_score_activity_stale_repo(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(
                is_git_repo=True,
                days_since_last_commit=400,
                commits_last_30_days=0,
                active_contributors_30d=0,
            ),
        )
        score = scorer._score_activity(metrics)
        assert score < 30

    def test_score_quality_good(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            quality=QualityMetrics(
                readme_exists=True,
                readme_quality=80,
                has_changelog=True,
                has_contributing=True,
                has_license=True,
                test_coverage_estimate=85,
                linting_configured=True,
                type_checking_configured=True,
            ),
        )
        score = scorer._score_quality(metrics)
        assert score >= 70

    def test_score_quality_poor(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            quality=QualityMetrics(
                readme_exists=False,
                test_coverage_estimate=0,
                code_duplication_ratio=40,
            ),
        )
        score = scorer._score_quality(metrics)
        assert score < 50

    def test_score_complexity_low(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            complexity=ComplexityMetrics(
                cyclomatic_complexity_avg=3,
                cyclomatic_complexity_max=10,
                maintainability_index=85,
                avg_function_length=15,
            ),
            code=CodeMetrics(avg_file_size=100),
        )
        score = scorer._score_complexity(metrics)
        assert score >= 70

    def test_score_complexity_high(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            complexity=ComplexityMetrics(
                cyclomatic_complexity_avg=20,
                cyclomatic_complexity_max=60,
                maintainability_index=15,
                avg_function_length=60,
            ),
            code=CodeMetrics(avg_file_size=600),
        )
        score = scorer._score_complexity(metrics)
        assert score < 30

    def test_score_security_perfect(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            security=SecurityMetrics(
                vulnerabilities_critical=0,
                vulnerabilities_high=0,
                secrets_detected=0,
                has_security_policy=True,
                has_dependabot=True,
                has_code_scanning=True,
            ),
            dependencies=DependencyMetrics(vulnerable_dependencies=0),
        )
        score = scorer._score_security(metrics)
        assert score >= 100  # 100 base + bonuses, capped at 100

    def test_score_security_critical_vulns(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            security=SecurityMetrics(
                vulnerabilities_critical=3,
                secrets_detected=2,
            ),
            dependencies=DependencyMetrics(vulnerable_dependencies=5),
        )
        score = scorer._score_security(metrics)
        assert score < 30

    def test_score_maintenance(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            dependencies=DependencyMetrics(
                dependency_freshness=85,
                total_dependencies=20,
                outdated_dependencies=2,
            ),
            tech_stack=TechStackMetrics(stack_modernity_score=75),
        )
        score = scorer._score_maintenance(metrics)
        assert score >= 70

    def test_calculate_score_returns_viability(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(
                is_git_repo=True,
                days_since_last_commit=3,
                commits_last_30_days=30,
                active_contributors_30d=3,
            ),
            quality=QualityMetrics(
                readme_exists=True,
                readme_quality=70,
                test_coverage_estimate=75,
                linting_configured=True,
            ),
            complexity=ComplexityMetrics(
                cyclomatic_complexity_avg=5,
                maintainability_index=70,
            ),
            security=SecurityMetrics(),
            dependencies=DependencyMetrics(
                dependency_freshness=70,
                total_dependencies=10,
            ),
            tech_stack=TechStackMetrics(
                primary_languages=["python"],
                stack_modernity_score=70,
            ),
        )
        result = scorer.calculate_score(metrics)
        assert 0 <= result.score <= 100
        assert result.grade in ("A+", "A", "B", "C", "D", "D-", "F")
        assert len(result.recommendation_text) > 0

    def test_score_potential_hot_topics(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            tech_stack=TechStackMetrics(
                primary_languages=["python", "rust"],
                frameworks=["svelte", "tauri"],
                stack_modernity_score=85,
            ),
        )
        score = scorer._score_potential(metrics)
        assert score >= 70  # Hot topics + modern stack

    def test_score_potential_no_tech(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            tech_stack=TechStackMetrics(
                primary_languages=[],
                frameworks=[],
                stack_modernity_score=30,
            ),
        )
        score = scorer._score_potential(metrics)
        assert 0 <= score <= 100

    def test_score_potential_with_ai_insights(self):
        from phantom.core.metrics_schema import AIInsights
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            tech_stack=TechStackMetrics(
                primary_languages=["python"],
                stack_modernity_score=70,
            ),
            ai_insights=AIInsights(
                strengths=["Good docs", "Active dev"],
                opportunities=["ML expansion"],
                weaknesses=["Limited tests"],
                threats=["Competition"],
            ),
        )
        score = scorer._score_potential(metrics)
        assert 0 <= score <= 100

    def test_generate_recommendation_text(self):
        from phantom.core.metrics_schema import ScoreBreakdown, ViabilityScore
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(
                is_git_repo=True,
                days_since_last_commit=5,
                commits_last_30_days=20,
                active_contributors_30d=2,
            ),
            quality=QualityMetrics(readme_exists=True, test_coverage_estimate=75),
            security=SecurityMetrics(),
        )
        breakdown = ScoreBreakdown(
            activity_score=80, quality_score=70, complexity_score=65,
            security_score=90, maintenance_score=60, potential_score=70,
        )
        vs = ViabilityScore.from_score(75.0, breakdown)
        recommendation = scorer.generate_recommendation(vs, metrics)
        assert "Investment Recommendation" in recommendation
        assert "Score Breakdown" in recommendation
        assert "Recommended Actions" in recommendation

    def test_generate_recommendation_with_weaknesses(self):
        from phantom.core.metrics_schema import ScoreBreakdown, ViabilityScore
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            activity=ActivityMetrics(
                is_git_repo=True,
                days_since_last_commit=200,
            ),
            security=SecurityMetrics(vulnerabilities_critical=3, secrets_detected=2),
            dependencies=DependencyMetrics(vulnerable_dependencies=5),
        )
        breakdown = ScoreBreakdown(
            activity_score=20, quality_score=30, complexity_score=25,
            security_score=15, maintenance_score=30, potential_score=40,
        )
        vs = ViabilityScore.from_score(25.0, breakdown)
        recommendation = scorer.generate_recommendation(vs, metrics)
        assert "Areas for Improvement" in recommendation
        assert "URGENT" in recommendation

    def test_score_maintenance_outdated_deps(self):
        scorer = ViabilityScorer()
        metrics = _make_metrics(
            dependencies=DependencyMetrics(
                dependency_freshness=15,
                total_dependencies=20,
                outdated_dependencies=15,
            ),
            tech_stack=TechStackMetrics(stack_modernity_score=20),
        )
        score = scorer._score_maintenance(metrics)
        assert score < 40

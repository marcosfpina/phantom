"""
Unit tests for the metrics schema module.

Tests Pydantic models: ProjectMetrics, ViabilityScore, ScoreBreakdown, etc.
"""

import pytest

from phantom.core.metrics_schema import (
    ActivityMetrics,
    CodeMetrics,
    ComplexityMetrics,
    DependencyMetrics,
    InvestmentRecommendation,
    ProjectMetrics,
    QualityMetrics,
    ScoreBreakdown,
    SecurityMetrics,
    TechStackMetrics,
    ViabilityScore,
)

pytestmark = pytest.mark.unit


class TestProjectMetrics:
    """Test ProjectMetrics construction and defaults."""

    def test_minimal_construction(self):
        pm = ProjectMetrics(
            project_id="test-001",
            name="TestProject",
            path="/tmp/test",
        )
        assert pm.project_id == "test-001"
        assert pm.name == "TestProject"
        assert pm.path == "/tmp/test"

    def test_default_sub_metrics(self):
        pm = ProjectMetrics(
            project_id="test-001",
            name="TestProject",
            path="/tmp/test",
        )
        assert isinstance(pm.code, CodeMetrics)
        assert isinstance(pm.activity, ActivityMetrics)
        assert isinstance(pm.quality, QualityMetrics)
        assert isinstance(pm.security, SecurityMetrics)
        assert isinstance(pm.dependencies, DependencyMetrics)
        assert isinstance(pm.tech_stack, TechStackMetrics)
        assert isinstance(pm.complexity, ComplexityMetrics)

    def test_ai_insights_default_none(self):
        pm = ProjectMetrics(project_id="x", name="x", path="/x")
        assert pm.ai_insights is None

    def test_errors_and_warnings_default_empty(self):
        pm = ProjectMetrics(project_id="x", name="x", path="/x")
        assert pm.errors == []
        assert pm.warnings == []


class TestScoreBreakdown:
    """Test ScoreBreakdown weighted_total calculation."""

    def test_weighted_total_all_zeros(self):
        bd = ScoreBreakdown()
        assert bd.weighted_total == 0.0

    def test_weighted_total_calculation(self):
        bd = ScoreBreakdown(
            activity_score=80, activity_weight=0.25,
            quality_score=70, quality_weight=0.20,
            complexity_score=60, complexity_weight=0.15,
            security_score=90, security_weight=0.15,
            maintenance_score=50, maintenance_weight=0.15,
            potential_score=40, potential_weight=0.10,
        )
        expected = (
            80 * 0.25
            + 70 * 0.20
            + 60 * 0.15
            + 90 * 0.15
            + 50 * 0.15
            + 40 * 0.10
        )
        assert abs(bd.weighted_total - expected) < 0.01

    def test_weighted_total_uniform_scores(self):
        bd = ScoreBreakdown(
            activity_score=100, activity_weight=0.25,
            quality_score=100, quality_weight=0.20,
            complexity_score=100, complexity_weight=0.15,
            security_score=100, security_weight=0.15,
            maintenance_score=100, maintenance_weight=0.15,
            potential_score=100, potential_weight=0.10,
        )
        assert abs(bd.weighted_total - 100.0) < 0.01


class TestViabilityScore:
    """Test ViabilityScore.from_score factory method."""

    @pytest.mark.parametrize(
        "score, expected_grade, expected_rec",
        [
            (95, "A+", InvestmentRecommendation.STRATEGIC_ASSET),
            (85, "A", InvestmentRecommendation.STRONG_PROJECT),
            (75, "B", InvestmentRecommendation.SOLID_FOUNDATION),
            (65, "C", InvestmentRecommendation.NEEDS_ATTENTION),
            (55, "D", InvestmentRecommendation.AT_RISK),
            (45, "D-", InvestmentRecommendation.CRITICAL),
            (30, "F", InvestmentRecommendation.LEGACY),
        ],
    )
    def test_grade_assignment(self, score, expected_grade, expected_rec):
        bd = ScoreBreakdown()
        vs = ViabilityScore.from_score(score, bd)
        assert vs.grade == expected_grade
        assert vs.recommendation == expected_rec

    def test_confidence_high_score(self):
        bd = ScoreBreakdown()
        vs = ViabilityScore.from_score(75, bd)
        assert vs.confidence == 0.8

    def test_confidence_low_score(self):
        bd = ScoreBreakdown()
        vs = ViabilityScore.from_score(25, bd)
        assert vs.confidence == 0.6

    def test_recommendation_text_set(self):
        bd = ScoreBreakdown()
        vs = ViabilityScore.from_score(90, bd)
        assert len(vs.recommendation_text) > 0


class TestCodeMetrics:
    """Test CodeMetrics defaults."""

    def test_defaults(self):
        cm = CodeMetrics()
        assert cm.total_lines == 0
        assert cm.code_lines == 0
        assert cm.file_count == 0
        assert cm.avg_file_size == 0.0
        assert cm.lines_by_language == {}


class TestActivityMetrics:
    """Test ActivityMetrics defaults."""

    def test_defaults(self):
        am = ActivityMetrics()
        assert am.is_git_repo is False
        assert am.days_since_last_commit == 999
        assert am.commits_last_30_days == 0
        assert am.total_contributors == 0


class TestSecurityMetrics:
    """Test SecurityMetrics defaults."""

    def test_defaults(self):
        sm = SecurityMetrics()
        assert sm.security_score == 100.0
        assert sm.vulnerabilities_critical == 0
        assert sm.secrets_detected == 0
        assert sm.has_security_policy is False

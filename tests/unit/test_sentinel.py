"""
Unit tests for the SENTINEL compliance integration module.

Tests: check_has_explanation, check_adr_traceability, check_recommendation_safety,
PhantomSentinel validation.
"""

import pytest

from phantom.neotron.sentinel_integration import (
    AgentOutput,
    ComplianceViolation,
    PhantomSentinel,
    check_adr_traceability,
    check_has_explanation,
    check_recommendation_safety,
)

pytestmark = pytest.mark.unit


def _make_output(
    content="Test recommendation",
    has_explanation=True,
    explanation="A detailed explanation for compliance",
    metadata=None,
):
    """Helper to build AgentOutput."""
    return AgentOutput(
        content=content,
        metadata=metadata or {},
        has_explanation=has_explanation,
        explanation=explanation,
    )


class TestCheckHasExplanation:
    """Test LGPD Art. 18 explanation check."""

    def test_with_explanation(self):
        output = _make_output(explanation="This is a valid explanation text.")
        result = check_has_explanation(output)
        assert result.passed is True

    def test_without_explanation(self):
        output = _make_output(has_explanation=False, explanation=None)
        result = check_has_explanation(output)
        assert result.passed is False
        assert "LGPD" in result.details

    def test_short_explanation(self):
        output = _make_output(explanation="short")
        result = check_has_explanation(output)
        assert result.passed is False
        assert "curta" in result.details.lower() or "quality" in result.details.lower()

    def test_empty_explanation(self):
        output = _make_output(has_explanation=True, explanation="")
        result = check_has_explanation(output)
        assert result.passed is False


class TestCheckADRTraceability:
    """Test SOC2 ADR traceability check."""

    def test_valid_adr_id(self):
        output = _make_output(metadata={"adr_id": "ADR-0023"})
        result = check_adr_traceability(output)
        assert result.passed is True
        assert "ADR-0023" in result.details

    def test_missing_adr_id(self):
        output = _make_output(metadata={})
        result = check_adr_traceability(output)
        assert result.passed is False
        assert "SOC2" in result.details

    def test_none_metadata(self):
        output = _make_output(metadata=None)
        result = check_adr_traceability(output)
        assert result.passed is False

    def test_invalid_adr_id_format(self):
        output = _make_output(metadata={"adr_id": "INVALID-123"})
        result = check_adr_traceability(output)
        assert result.passed is False
        assert "formato" in result.details.lower() or "format" in result.details.lower()

    def test_empty_adr_id(self):
        output = _make_output(metadata={"adr_id": ""})
        result = check_adr_traceability(output)
        assert result.passed is False


class TestCheckRecommendationSafety:
    """Test recommendation safety check."""

    def test_safe_recommendation(self):
        output = _make_output(content="Check system ventilation and reduce workload")
        result = check_recommendation_safety(output)
        assert result.passed is True

    def test_dangerous_rm_rf(self):
        output = _make_output(content="Execute: rm -rf / to clean cache")
        result = check_recommendation_safety(output)
        assert result.passed is False
        assert "rm -rf /" in result.metadata["dangerous_pattern"]

    def test_dangerous_dd(self):
        output = _make_output(content="Run dd if=/dev/zero of=/dev/sda")
        result = check_recommendation_safety(output)
        assert result.passed is False

    def test_dangerous_kill_init(self):
        output = _make_output(content="kill -9 1")
        result = check_recommendation_safety(output)
        assert result.passed is False

    def test_dangerous_forced_reboot(self):
        output = _make_output(content="reboot -f")
        result = check_recommendation_safety(output)
        assert result.passed is False


class TestPhantomSentinel:
    """Test the full SENTINEL validation engine."""

    def test_validate_all_passing(self):
        sentinel = PhantomSentinel()
        result = sentinel.validate(
            recommendation="Check system ventilation",
            adr_id="ADR-0023",
            explanation="Based on thermal analysis, temperature exceeds safe threshold",
        )
        assert result.validation_result.passed is True
        meta = result.validation_result.metadata
        assert meta["total_guardrails"] == 3
        assert meta["passed"] == 3
        assert meta["failed"] == 0

    def test_validate_missing_explanation(self):
        sentinel = PhantomSentinel()
        with pytest.raises(ComplianceViolation) as exc_info:
            sentinel.validate(
                recommendation="Restart system",
                adr_id="ADR-0001",
                explanation=None,
            )
        assert "phantom_explanation_required" in str(exc_info.value)

    def test_validate_missing_adr(self):
        sentinel = PhantomSentinel()
        with pytest.raises(ComplianceViolation) as exc_info:
            sentinel.validate(
                recommendation="Increase swap",
                adr_id=None,
                explanation="System has low memory available",
            )
        assert "phantom_adr_traceability" in str(exc_info.value)

    def test_validate_dangerous_command(self):
        sentinel = PhantomSentinel()
        with pytest.raises(ComplianceViolation) as exc_info:
            sentinel.validate(
                recommendation="Execute: rm -rf / to clean cache",
                adr_id="ADR-0001",
                explanation="Cleaning disk space",
            )
        assert "phantom_safety_check" in str(exc_info.value)

    def test_guardrail_name(self):
        sentinel = PhantomSentinel()
        result = sentinel.validate(
            recommendation="Test",
            adr_id="ADR-0001",
            explanation="Valid explanation text here",
        )
        assert result.guardrail_name == "phantom_sentinel_suite"

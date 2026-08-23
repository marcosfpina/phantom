"""
Unit tests for the ORACLE explainer module.

Tests: OracleExplainer, evidence extraction, confidence calculation.
"""

import pytest

from phantom.neotron.oracle_explainer import ADRExplanation, Evidence, OracleExplainer

pytestmark = pytest.mark.unit


class TestEvidence:
    """Test Evidence dataclass."""

    def test_construction(self):
        e = Evidence(
            metric_name="temperature",
            value=85.0,
            threshold=75.0,
            severity="critical",
        )
        assert e.metric_name == "temperature"
        assert e.value == 85.0
        assert e.severity == "critical"


class TestOracleExplainer:
    """Test the Oracle explainer engine."""

    def setup_method(self):
        self.oracle = OracleExplainer()

    def test_explain_recommendation_basic(self):
        explanation = self.oracle.explain_recommendation(
            adr_id="ADR-0023",
            adr_title="Thermal Management",
            match_score=0.85,
            metrics={},
        )
        assert isinstance(explanation, ADRExplanation)
        assert explanation.adr_id == "ADR-0023"
        assert explanation.match_score == 0.85
        assert len(explanation.explanation) > 0

    def test_explain_recommendation_with_metrics(self):
        metrics = {
            "thermal": {"max_temp_celsius": 90},
            "memory": {"usage_percent": 92},
            "cpu": {"usage_percent": 96},
        }
        explanation = self.oracle.explain_recommendation(
            adr_id="ADR-0001",
            adr_title="System Health",
            match_score=0.7,
            metrics=metrics,
        )
        assert len(explanation.evidences) > 0
        assert explanation.confidence > 0.7

    def test_explain_recommendation_with_alerts(self):
        alerts = [
            {"severity": "Critical", "category": "Thermal", "message": "High temp"},
        ]
        explanation = self.oracle.explain_recommendation(
            adr_id="ADR-0005",
            adr_title="Alert Response",
            match_score=0.6,
            metrics={},
            alerts=alerts,
        )
        alert_evidences = [
            e for e in explanation.evidences
            if e.metric_name.startswith("alert_")
        ]
        assert len(alert_evidences) > 0

    def test_explain_multiple(self):
        recommendations = [
            {"id": "ADR-0023", "title": "Thermal Management", "score": 0.89},
            {"id": "ADR-0011", "title": "Memory Optimization", "score": 0.76},
        ]
        metrics = {"thermal": {"max_temp_celsius": 82}}
        explanations = self.oracle.explain_multiple(recommendations, metrics)
        assert len(explanations) == 2
        assert explanations[0].adr_id == "ADR-0023"
        assert explanations[1].adr_id == "ADR-0011"


class TestEvidenceExtraction:
    """Test _extract_evidences for different metric types."""

    def setup_method(self):
        self.oracle = OracleExplainer()

    def test_thermal_critical(self):
        metrics = {"thermal": {"max_temp_celsius": 90}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "temperature" and e.severity == "critical" for e in evidences)

    def test_thermal_warning(self):
        metrics = {"thermal": {"max_temp_celsius": 80}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "temperature" and e.severity == "warning" for e in evidences)

    def test_thermal_normal(self):
        metrics = {"thermal": {"max_temp_celsius": 60}}
        evidences = self.oracle._extract_evidences(metrics, [])
        thermal = [e for e in evidences if e.metric_name == "temperature"]
        assert len(thermal) == 0

    def test_memory_critical(self):
        metrics = {"memory": {"usage_percent": 95}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "memory_usage" and e.severity == "critical" for e in evidences)

    def test_memory_warning(self):
        metrics = {"memory": {"usage_percent": 87}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "memory_usage" and e.severity == "warning" for e in evidences)

    def test_cpu_critical(self):
        metrics = {"cpu": {"usage_percent": 97}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "cpu_usage" and e.severity == "critical" for e in evidences)

    def test_cpu_warning(self):
        metrics = {"cpu": {"usage_percent": 92}}
        evidences = self.oracle._extract_evidences(metrics, [])
        assert any(e.metric_name == "cpu_usage" and e.severity == "warning" for e in evidences)

    def test_alert_evidence(self):
        alerts = [
            {"severity": "Critical", "category": "Disk", "message": "Low space"},
        ]
        evidences = self.oracle._extract_evidences({}, alerts)
        assert any(e.metric_name == "alert_Disk" for e in evidences)

    def test_no_evidence_for_normal_metrics(self):
        metrics = {
            "thermal": {"max_temp_celsius": 50},
            "memory": {"usage_percent": 40},
            "cpu": {"usage_percent": 30},
        }
        evidences = self.oracle._extract_evidences(metrics, [])
        assert len(evidences) == 0


class TestConfidenceCalculation:
    """Test _calculate_confidence scoring."""

    def setup_method(self):
        self.oracle = OracleExplainer()

    def test_base_score_is_match_score(self):
        confidence = self.oracle._calculate_confidence(0.5, [])
        assert confidence == 0.5

    def test_evidence_bonus(self):
        evidences = [
            Evidence("temp", 80.0, 75.0, "warning"),
            Evidence("mem", 90.0, 85.0, "warning"),
        ]
        confidence = self.oracle._calculate_confidence(0.5, evidences)
        assert confidence > 0.5

    def test_critical_bonus(self):
        evidences = [
            Evidence("temp", 90.0, 85.0, "critical"),
        ]
        confidence = self.oracle._calculate_confidence(0.5, evidences)
        # Should get both evidence bonus and critical bonus
        assert confidence > 0.55

    def test_capped_at_1(self):
        evidences = [Evidence(f"m{i}", 100.0, 50.0, "critical") for i in range(20)]
        confidence = self.oracle._calculate_confidence(0.9, evidences)
        assert confidence <= 1.0

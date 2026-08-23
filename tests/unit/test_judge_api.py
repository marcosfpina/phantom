"""
Unit tests for the Judge API module.

Tests: Pydantic models, JudgmentEngine analysis.
"""

import pytest

from phantom.api.judge_api import (
    Alert,
    CPUMetrics,
    JudgmentEngine,
    LogEntry,
    MemoryMetrics,
    PhantomGateBundle,
    PhantomGateResponse,
    SystemMetrics,
    ThermalMetrics,
)

pytestmark = pytest.mark.unit


def _make_bundle(
    cpu_percent=50.0,
    mem_percent=50.0,
    max_temp=60.0,
    alerts=None,
    logs=None,
):
    """Helper to build a PhantomGateBundle."""
    return PhantomGateBundle(
        timestamp=1700000000,
        hostname="test-host",
        metrics=SystemMetrics(
            cpu=CPUMetrics(usage_percent=cpu_percent, cores=[cpu_percent]),
            memory=MemoryMetrics(
                total_bytes=16_000_000_000,
                used_bytes=int(16_000_000_000 * mem_percent / 100),
                usage_percent=mem_percent,
            ),
            thermal=ThermalMetrics(
                max_temp_celsius=max_temp,
                avg_temp_celsius=max_temp - 5,
            ),
        ),
        alerts=alerts or [],
        logs=logs or [],
    )


class TestPydanticModels:
    """Test judge_api Pydantic model construction."""

    def test_cpu_metrics(self):
        cpu = CPUMetrics(usage_percent=75.5, cores=[80.0, 71.0])
        assert cpu.usage_percent == 75.5
        assert len(cpu.cores) == 2

    def test_memory_metrics(self):
        mem = MemoryMetrics(
            total_bytes=16_000_000_000,
            used_bytes=12_000_000_000,
            usage_percent=75.0,
        )
        assert mem.usage_percent == 75.0

    def test_thermal_metrics(self):
        thermal = ThermalMetrics(max_temp_celsius=80.0, avg_temp_celsius=72.0)
        assert thermal.max_temp_celsius == 80.0

    def test_alert_model(self):
        alert = Alert(
            timestamp=1700000000,
            severity="Critical",
            category="Thermal",
            message="High temperature detected",
        )
        assert alert.severity == "Critical"
        assert alert.details is None

    def test_log_entry(self):
        log = LogEntry(
            timestamp=1700000000,
            priority="error",
            unit="systemd",
            message="Service failed",
        )
        assert log.priority == "error"

    def test_bundle_construction(self):
        bundle = _make_bundle()
        assert bundle.hostname == "test-host"
        assert bundle.timestamp == 1700000000

    def test_response_model(self):
        resp = PhantomGateResponse(
            severity="info",
            insights=["All normal"],
            relevant_adrs=[],
            recommendations=["Continue monitoring"],
            bundle_file="/tmp/test.json",
        )
        assert resp.severity == "info"
        assert resp.notes == []


class TestJudgmentEngine:
    """Test JudgmentEngine analysis logic."""

    def test_normal_metrics_info_severity(self):
        engine = JudgmentEngine()
        bundle = _make_bundle(cpu_percent=50, mem_percent=50, max_temp=60)
        result = engine.judge(bundle)
        assert result.severity == "info"
        assert len(result.insights) == 0

    def test_high_temperature_warning(self):
        engine = JudgmentEngine()
        bundle = _make_bundle(max_temp=82)
        result = engine.judge(bundle)
        assert result.severity == "warning"
        assert any("temperatura" in i.lower() or "temp" in i.lower() for i in result.insights)

    def test_high_memory_warning(self):
        engine = JudgmentEngine()
        bundle = _make_bundle(mem_percent=90)
        result = engine.judge(bundle)
        assert result.severity == "warning"
        assert any("mem" in i.lower() for i in result.insights)

    def test_high_cpu_warning(self):
        engine = JudgmentEngine()
        bundle = _make_bundle(cpu_percent=95)
        result = engine.judge(bundle)
        assert result.severity == "warning"
        assert any("cpu" in i.lower() for i in result.insights)

    def test_critical_alerts_escalate_severity(self):
        engine = JudgmentEngine()
        alert = Alert(
            timestamp=1700000000,
            severity="Critical",
            category="Thermal",
            message="System overheating",
        )
        bundle = _make_bundle(alerts=[alert])
        result = engine.judge(bundle)
        assert result.severity == "critical"

    def test_multiple_issues(self):
        engine = JudgmentEngine()
        bundle = _make_bundle(cpu_percent=95, mem_percent=90, max_temp=82)
        result = engine.judge(bundle)
        assert result.severity == "warning"
        assert len(result.insights) >= 3
        assert len(result.recommendations) >= 3

    def test_bundle_saved(self):
        engine = JudgmentEngine()
        bundle = _make_bundle()
        result = engine.judge(bundle)
        assert result.bundle_file.endswith(".json")
        assert "phantom-bundles" in result.bundle_dir

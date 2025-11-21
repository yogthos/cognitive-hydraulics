"""Unit tests for MetaCognitiveMonitor thinking output."""

import pytest

from cognitive_hydraulics.engine.meta_monitor import (
    MetaCognitiveMonitor,
    CognitiveMetrics,
)


class TestMetaCognitiveMonitorThinking:
    """Tests for thinking output in MetaCognitiveMonitor."""

    def test_get_thinking_summary_calm(self):
        """Test thinking summary for calm pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=3, time_threshold_ms=500.0)
        metrics = CognitiveMetrics(
            goal_depth=0,
            time_in_state_ms=50.0,
            impasse_count=0,
            operator_ambiguity=0.2,
        )

        summary = monitor.get_thinking_summary(metrics)

        assert "Depth: 0/3" in summary
        assert "Time in state: 50ms" in summary
        assert "Impasses: 0" in summary
        assert "Ambiguity: 0.20" in summary
        assert "CALM" in summary
        assert "continuing with Soar" in summary

    def test_get_thinking_summary_high_pressure(self):
        """Test thinking summary for high pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=3, time_threshold_ms=500.0)
        metrics = CognitiveMetrics(
            goal_depth=2,
            time_in_state_ms=400.0,
            impasse_count=2,
            operator_ambiguity=0.8,
        )

        summary = monitor.get_thinking_summary(metrics)

        assert "Depth: 2/3" in summary
        assert "Time in state: 400ms" in summary
        assert "Impasses: 2" in summary
        assert "Ambiguity: 0.80" in summary
        assert "HIGH" in summary or "ELEVATED" in summary

    def test_get_thinking_summary_critical_pressure(self):
        """Test thinking summary for critical pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=3, time_threshold_ms=500.0)
        metrics = CognitiveMetrics(
            goal_depth=3,
            time_in_state_ms=600.0,
            impasse_count=3,
            operator_ambiguity=1.0,
        )

        summary = monitor.get_thinking_summary(metrics)

        assert "CRITICAL" in summary
        assert "triggering ACT-R fallback" in summary

    def test_get_thinking_summary_includes_pressure_breakdown(self):
        """Test that thinking summary includes pressure calculation breakdown."""
        monitor = MetaCognitiveMonitor(depth_threshold=5, time_threshold_ms=1000.0)
        metrics = CognitiveMetrics(
            goal_depth=2,
            time_in_state_ms=300.0,
            impasse_count=1,
            operator_ambiguity=0.5,
        )

        summary = monitor.get_thinking_summary(metrics)

        # Should show individual components
        assert "Depth:" in summary
        assert "Time in state:" in summary
        assert "Impasses:" in summary
        assert "Ambiguity:" in summary
        assert "Pressure:" in summary
        assert "Decision:" in summary


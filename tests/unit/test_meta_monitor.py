"""Unit tests for MetaCognitiveMonitor."""

import time
import pytest

from cognitive_hydraulics.engine.meta_monitor import (
    MetaCognitiveMonitor,
    CognitiveMetrics,
)
from cognitive_hydraulics.operators.file_ops import OpReadFile


class TestCognitiveMetrics:
    """Tests for CognitiveMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating cognitive metrics."""
        metrics = CognitiveMetrics(
            goal_depth=2,
            time_in_state_ms=300.0,
            impasse_count=1,
            operator_ambiguity=0.5,
        )

        assert metrics.goal_depth == 2
        assert metrics.time_in_state_ms == 300.0
        assert metrics.impasse_count == 1
        assert metrics.operator_ambiguity == 0.5


class TestMetaCognitiveMonitor:
    """Tests for MetaCognitiveMonitor."""

    def test_create_monitor(self):
        """Test creating monitor with default thresholds."""
        monitor = MetaCognitiveMonitor()

        assert monitor.depth_threshold == 3
        assert monitor.time_threshold_ms == 500.0
        assert monitor.total_impasses == 0

    def test_create_monitor_custom_thresholds(self):
        """Test creating monitor with custom thresholds."""
        monitor = MetaCognitiveMonitor(depth_threshold=5, time_threshold_ms=1000.0)

        assert monitor.depth_threshold == 5
        assert monitor.time_threshold_ms == 1000.0

    def test_reset_timer(self):
        """Test resetting the state timer."""
        monitor = MetaCognitiveMonitor()

        # Wait a bit
        time.sleep(0.1)
        old_time = monitor.get_time_in_state_ms()
        assert old_time > 50  # At least 50ms passed

        # Reset
        monitor.reset_timer()
        new_time = monitor.get_time_in_state_ms()
        assert new_time < old_time  # Timer reset

    def test_increment_impasse_count(self):
        """Test incrementing impasse counter."""
        monitor = MetaCognitiveMonitor()

        assert monitor.total_impasses == 0

        monitor.increment_impasse_count()
        assert monitor.total_impasses == 1

        monitor.increment_impasse_count()
        assert monitor.total_impasses == 2

    def test_calculate_pressure_low(self):
        """Test calculating low pressure."""
        monitor = MetaCognitiveMonitor()

        metrics = CognitiveMetrics(
            goal_depth=0,
            time_in_state_ms=100.0,
            impasse_count=0,
            operator_ambiguity=0.0,
        )

        pressure = monitor.calculate_pressure(metrics)

        assert 0.0 <= pressure < 0.3  # Low pressure

    def test_calculate_pressure_high(self):
        """Test calculating high pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=3, time_threshold_ms=500.0)

        metrics = CognitiveMetrics(
            goal_depth=3,  # At threshold
            time_in_state_ms=600.0,  # Over threshold
            impasse_count=3,
            operator_ambiguity=1.0,  # Complete ambiguity
        )

        pressure = monitor.calculate_pressure(metrics)

        assert pressure >= 0.7  # High pressure

    def test_should_trigger_fallback_false(self):
        """Test fallback not triggered at low pressure."""
        monitor = MetaCognitiveMonitor()

        metrics = CognitiveMetrics(
            goal_depth=1,
            time_in_state_ms=100.0,
            impasse_count=0,
            operator_ambiguity=0.2,
        )

        assert not monitor.should_trigger_fallback(metrics)

    def test_should_trigger_fallback_true(self):
        """Test fallback triggered at high pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=2)

        metrics = CognitiveMetrics(
            goal_depth=3,  # Over threshold
            time_in_state_ms=1000.0,
            impasse_count=5,
            operator_ambiguity=0.9,
        )

        assert monitor.should_trigger_fallback(metrics)

    def test_calculate_operator_ambiguity_no_operators(self):
        """Test ambiguity with no operators."""
        monitor = MetaCognitiveMonitor()

        ambiguity = monitor.calculate_operator_ambiguity([])

        assert ambiguity == 1.0  # Complete ambiguity

    def test_calculate_operator_ambiguity_one_operator(self):
        """Test ambiguity with single operator."""
        monitor = MetaCognitiveMonitor()

        operators = [(OpReadFile("test.py"), 5.0)]
        ambiguity = monitor.calculate_operator_ambiguity(operators)

        assert ambiguity == 0.0  # No ambiguity

    def test_calculate_operator_ambiguity_clear_winner(self):
        """Test ambiguity with clear winner."""
        monitor = MetaCognitiveMonitor()

        operators = [
            (OpReadFile("best.py"), 10.0),
            (OpReadFile("worse.py"), 1.0),
        ]
        ambiguity = monitor.calculate_operator_ambiguity(operators)

        assert 0.0 <= ambiguity < 0.3  # Low ambiguity

    def test_calculate_operator_ambiguity_tie(self):
        """Test ambiguity with perfect tie."""
        monitor = MetaCognitiveMonitor()

        operators = [
            (OpReadFile("a.py"), 5.0),
            (OpReadFile("b.py"), 5.0),
            (OpReadFile("c.py"), 5.0),
        ]
        ambiguity = monitor.calculate_operator_ambiguity(operators)

        assert ambiguity == 1.0  # Maximum ambiguity

    def test_get_status_summary_calm(self):
        """Test status summary at low pressure."""
        monitor = MetaCognitiveMonitor()

        metrics = CognitiveMetrics(
            goal_depth=0,
            time_in_state_ms=100.0,
            impasse_count=0,
            operator_ambiguity=0.1,
        )

        summary = monitor.get_status_summary(metrics)

        assert "CALM" in summary
        assert "0.1" in summary or "0.2" in summary  # Low pressure

    def test_get_status_summary_critical(self):
        """Test status summary at critical pressure."""
        monitor = MetaCognitiveMonitor(depth_threshold=2)

        metrics = CognitiveMetrics(
            goal_depth=3,
            time_in_state_ms=1000.0,
            impasse_count=5,
            operator_ambiguity=1.0,
        )

        summary = monitor.get_status_summary(metrics)

        assert "CRITICAL" in summary

    def test_time_measurement(self):
        """Test that time measurement works."""
        monitor = MetaCognitiveMonitor()

        time.sleep(0.05)  # 50ms
        elapsed = monitor.get_time_in_state_ms()

        assert 40 <= elapsed <= 100  # Allow some variation

    def test_pressure_components_weighted(self):
        """Test that pressure components are properly weighted."""
        monitor = MetaCognitiveMonitor(depth_threshold=10)

        # Test pure depth pressure
        depth_metrics = CognitiveMetrics(
            goal_depth=10, time_in_state_ms=0, impasse_count=0, operator_ambiguity=0
        )
        depth_pressure = monitor.calculate_pressure(depth_metrics)

        # Test pure time pressure
        time_metrics = CognitiveMetrics(
            goal_depth=0, time_in_state_ms=500, impasse_count=0, operator_ambiguity=0
        )
        time_pressure = monitor.calculate_pressure(time_metrics)

        # Test pure ambiguity pressure
        ambiguity_metrics = CognitiveMetrics(
            goal_depth=0, time_in_state_ms=0, impasse_count=0, operator_ambiguity=1.0
        )
        ambiguity_pressure = monitor.calculate_pressure(ambiguity_metrics)

        # All should contribute but with different weights
        assert depth_pressure > 0
        assert time_pressure > 0
        assert ambiguity_pressure > 0


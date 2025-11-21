"""Meta-cognitive monitoring for detecting cognitive overload."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from cognitive_hydraulics.core.operator import Operator


@dataclass
class CognitiveMetrics:
    """Tracks cognitive load indicators."""

    goal_depth: int  # How many sub-goals deep
    time_in_state_ms: float  # How long stuck in current state
    impasse_count: int  # How many impasses encountered
    operator_ambiguity: float  # 0.0 = clear winner, 1.0 = all equal

    def __repr__(self) -> str:
        return (
            f"CognitiveMetrics(depth={self.goal_depth}, "
            f"time={self.time_in_state_ms:.0f}ms, "
            f"impasses={self.impasse_count}, "
            f"ambiguity={self.operator_ambiguity:.2f})"
        )


class MetaCognitiveMonitor:
    """
    Watches for cognitive overload and triggers fallback.

    Implements the "pressure valve" that switches from Soar
    (System 2) to ACT-R (System 1) when reasoning becomes too costly.
    """

    def __init__(
        self, depth_threshold: int = 3, time_threshold_ms: float = 500.0
    ):
        """
        Initialize the monitor.

        Args:
            depth_threshold: Max sub-goal depth before fallback
            time_threshold_ms: Max time in state before fallback
        """
        self.depth_threshold = depth_threshold
        self.time_threshold_ms = time_threshold_ms
        self.state_entry_time = time.time()
        self.total_impasses = 0

    def reset_timer(self) -> None:
        """Reset the state timer (call when state changes)."""
        self.state_entry_time = time.time()

    def increment_impasse_count(self) -> None:
        """Increment the total impasse counter."""
        self.total_impasses += 1

    def get_time_in_state_ms(self) -> float:
        """Get milliseconds elapsed since entering current state."""
        return (time.time() - self.state_entry_time) * 1000

    def calculate_pressure(self, metrics: CognitiveMetrics) -> float:
        """
        Calculate cognitive pressure (0.0 = calm, 1.0 = panic).

        Pressure increases with:
        - Goal depth (recursive sub-goaling)
        - Time stuck in same state
        - Number of impasses encountered
        - Ambiguity in operator selection

        Args:
            metrics: Current cognitive metrics

        Returns:
            Pressure value 0.0 to 1.0+
        """
        # Depth pressure: increases as we nest sub-goals
        depth_pressure = min(metrics.goal_depth / self.depth_threshold, 1.0)

        # Time pressure: increases as we stay in same state
        time_pressure = min(
            metrics.time_in_state_ms / self.time_threshold_ms, 1.0
        )

        # Impasse pressure: too many impasses = we're stuck
        impasse_pressure = min(metrics.impasse_count / 3.0, 1.0)

        # Ambiguity pressure: can't decide between operators
        ambiguity_pressure = metrics.operator_ambiguity

        # Weighted combination
        # Depth and ambiguity are most important
        pressure = (
            0.35 * depth_pressure
            + 0.25 * time_pressure
            + 0.20 * impasse_pressure
            + 0.20 * ambiguity_pressure
        )

        return pressure

    def should_trigger_fallback(self, metrics: CognitiveMetrics) -> bool:
        """
        Should we abandon symbolic reasoning and use ACT-R fallback?

        Args:
            metrics: Current cognitive metrics

        Returns:
            True if pressure is too high
        """
        pressure = self.calculate_pressure(metrics)
        return pressure >= 0.7  # Threshold for panic

    def calculate_operator_ambiguity(
        self, operators: List[tuple[Operator, float]]
    ) -> float:
        """
        Calculate how ambiguous the operator choice is.

        Args:
            operators: List of (operator, priority) tuples

        Returns:
            Ambiguity score 0.0 (clear winner) to 1.0 (all equal)
        """
        if not operators:
            return 1.0  # Complete ambiguity - no options

        if len(operators) == 1:
            return 0.0  # No ambiguity - clear winner

        priorities = [priority for _, priority in operators]
        max_priority = max(priorities)
        min_priority = min(priorities)

        if max_priority == min_priority:
            return 1.0  # All equal - maximum ambiguity

        # Calculate spread
        priority_range = max_priority - min_priority
        # Count how many are close to the top
        top_contenders = sum(
            1 for p in priorities if p >= max_priority - (priority_range * 0.1)
        )

        # More top contenders = more ambiguity
        ambiguity = (top_contenders - 1) / len(operators)
        return ambiguity

    def get_status_summary(self, metrics: CognitiveMetrics) -> str:
        """
        Get a human-readable summary of cognitive status.

        Args:
            metrics: Current cognitive metrics

        Returns:
            Status string
        """
        pressure = self.calculate_pressure(metrics)

        if pressure < 0.3:
            status = "🟢 CALM"
        elif pressure < 0.5:
            status = "🟡 ELEVATED"
        elif pressure < 0.7:
            status = "🟠 HIGH"
        else:
            status = "🔴 CRITICAL"

        return (
            f"{status} - Pressure: {pressure:.2f} | "
            f"Depth: {metrics.goal_depth}/{self.depth_threshold} | "
            f"Time: {metrics.time_in_state_ms:.0f}ms | "
            f"Ambiguity: {metrics.operator_ambiguity:.2f}"
        )

    def get_thinking_summary(self, metrics: CognitiveMetrics) -> str:
        """
        Get detailed thinking breakdown of pressure calculation.

        Args:
            metrics: Current cognitive metrics

        Returns:
            Multi-line string with pressure breakdown
        """
        pressure = self.calculate_pressure(metrics)

        # Calculate individual components
        depth_pressure = min(metrics.goal_depth / self.depth_threshold, 1.0)
        time_pressure = min(metrics.time_in_state_ms / self.time_threshold_ms, 1.0)
        impasse_pressure = min(metrics.impasse_count / 3.0, 1.0)
        ambiguity_pressure = metrics.operator_ambiguity

        # Determine status
        if pressure < 0.3:
            status = "CALM"
            decision = "continuing with Soar"
        elif pressure < 0.5:
            status = "ELEVATED"
            decision = "continuing with Soar"
        elif pressure < 0.7:
            status = "HIGH"
            decision = "continuing with Soar (approaching threshold)"
        else:
            status = "CRITICAL"
            decision = "triggering ACT-R fallback"

        lines = [
            f"Depth: {metrics.goal_depth}/{self.depth_threshold} ({depth_pressure:.2f})",
            f"Time in state: {metrics.time_in_state_ms:.0f}ms ({time_pressure:.2f})",
            f"Impasses: {metrics.impasse_count} ({impasse_pressure:.2f})",
            f"Ambiguity: {metrics.operator_ambiguity:.2f}",
            f"Pressure: {pressure:.2f} ({status})",
            f"Decision: {decision}",
        ]

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"MetaCognitiveMonitor(depth_threshold={self.depth_threshold}, "
            f"time_threshold={self.time_threshold_ms}ms, "
            f"impasses={self.total_impasses})"
        )


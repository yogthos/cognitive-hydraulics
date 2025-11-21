"""Impasse detection and handling."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.core.state import Goal


class ImpasseType(Enum):
    """Types of impasses in the Soar decision cycle."""

    NO_CHANGE = "no_change"  # No operators proposed
    TIE = "tie"  # Multiple operators with equal priority
    CONFLICT = "conflict"  # Multiple operators, can't decide
    OPERATOR_NO_CHANGE = "operator_no_change"  # Operator selected but can't apply


@dataclass
class Impasse:
    """Represents a decision-making impasse."""

    type: ImpasseType
    goal: Goal
    operators: List[Operator]
    description: str

    def __repr__(self) -> str:
        return (
            f"Impasse({self.type.value}, "
            f"{len(self.operators)} operators, "
            f"goal='{self.goal.description[:30]}...')"
        )


class ImpasseDetector:
    """Detects when the system is stuck and needs special handling."""

    @staticmethod
    def detect_impasse(
        operators: List[tuple[Operator, float]], goal: Goal
    ) -> Optional[Impasse]:
        """
        Detect if current situation is an impasse.

        Args:
            operators: List of (operator, priority) tuples
            goal: Current goal

        Returns:
            Impasse object or None if no impasse
        """
        # No operators proposed = NO CHANGE impasse
        if not operators:
            return Impasse(
                type=ImpasseType.NO_CHANGE,
                goal=goal,
                operators=[],
                description="No operators were proposed by any rules",
            )

        # Single operator = no impasse
        if len(operators) == 1:
            return None

        # Multiple operators - check if it's a tie
        priorities = [priority for _, priority in operators]
        max_priority = max(priorities)

        # Count operators at max priority
        top_operators = [
            op for op, pri in operators if pri == max_priority
        ]

        # If multiple operators have same top priority = TIE
        if len(top_operators) > 1:
            return Impasse(
                type=ImpasseType.TIE,
                goal=goal,
                operators=top_operators,
                description=f"{len(top_operators)} operators tied at priority {max_priority}",
            )

        # Otherwise, clear winner - no impasse
        return None

    @staticmethod
    def create_subgoal_from_impasse(impasse: Impasse) -> Goal:
        """
        Create a sub-goal to resolve the impasse.

        Args:
            impasse: The impasse to resolve

        Returns:
            New sub-goal
        """
        if impasse.type == ImpasseType.NO_CHANGE:
            # Need to figure out what to do
            subgoal = Goal(
                description=f"Determine action for: {impasse.goal.description}",
                parent_goal=impasse.goal,
                status="active",
                priority=impasse.goal.priority + 0.1,
            )
        elif impasse.type == ImpasseType.TIE:
            # Need to break the tie
            operator_names = [op.name for op in impasse.operators]
            subgoal = Goal(
                description=f"Choose between: {', '.join(operator_names)}",
                parent_goal=impasse.goal,
                status="active",
                priority=impasse.goal.priority + 0.1,
            )
        else:
            # Generic conflict resolution
            subgoal = Goal(
                description=f"Resolve {impasse.type.value} for: {impasse.goal.description}",
                parent_goal=impasse.goal,
                status="active",
                priority=impasse.goal.priority + 0.1,
            )

        # Link back to parent
        impasse.goal.sub_goals.append(subgoal)

        return subgoal


"""Working memory for tracking state history and transitions."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator, OperatorResult


class StateTransition(BaseModel):
    """Represents a state transition caused by an operator."""

    timestamp: datetime
    previous_state: EditorState
    operator: str  # Operator name (can't store Operator directly - not serializable)
    result: OperatorResult
    new_state: EditorState
    goal_at_time: Goal


class WorkingMemory:
    """
    Working memory tracks the history of states and transitions.

    This is crucial for:
    - Learning from successful sequences
    - Undoing failed operations
    - Explaining decision chains
    - Detecting loops (trying the same thing repeatedly)
    """

    def __init__(self, initial_state: EditorState, initial_goal: Goal):
        self.initial_state = initial_state
        self.current_state = initial_state
        self.current_goal = initial_goal
        self.history: List[StateTransition] = []
        self.max_history_size = 1000  # Prevent unbounded growth

    def record_transition(
        self,
        operator: Operator,
        result: OperatorResult,
        new_state: EditorState,
        current_goal: Goal,
    ) -> None:
        """Record a state transition."""
        transition = StateTransition(
            timestamp=datetime.now(),
            previous_state=self.current_state,
            operator=operator.name,
            result=result,
            new_state=new_state,
            goal_at_time=current_goal,
        )

        self.history.append(transition)
        self.current_state = new_state

        # Trim history if too large
        if len(self.history) > self.max_history_size:
            self.history = self.history[-self.max_history_size :]

    def get_recent_transitions(self, n: int = 10) -> List[StateTransition]:
        """Get the N most recent transitions."""
        return self.history[-n:]

    def get_failed_operators(self, window: int = 20) -> List[str]:
        """Get list of operators that failed in recent history."""
        recent = self.get_recent_transitions(window)
        return [t.operator for t in recent if not t.result.success]

    def has_loop(self, window: int = 5) -> bool:
        """
        Detect if we're stuck in a loop (same operator failing repeatedly).

        Returns True if the same operator has failed multiple times recently.
        """
        if len(self.history) < 3:
            return False

        recent = self.get_recent_transitions(window)
        failed_ops = [t.operator for t in recent if not t.result.success]

        if not failed_ops:
            return False

        # If same operator failed 3+ times in window, we're looping
        from collections import Counter

        counts = Counter(failed_ops)
        return any(count >= 3 for count in counts.values())

    def rollback(self, steps: int = 1) -> EditorState:
        """
        Rollback to a previous state.

        Returns the state from `steps` transitions ago.
        """
        if steps > len(self.history):
            return self.initial_state

        target_idx = len(self.history) - steps
        return self.history[target_idx].previous_state

    def get_trace(self) -> str:
        """
        Generate a human-readable trace of all transitions.

        Useful for debugging and explaining the reasoning process.
        """
        lines = [f"Initial State: {self.initial_state.working_directory}"]
        lines.append(f"Goal: {self.current_goal.description}\n")

        for i, transition in enumerate(self.history, 1):
            status = "✓" if transition.result.success else "✗"
            lines.append(f"{i}. {status} {transition.operator}")
            lines.append(f"   {transition.result.output}")
            if transition.result.error:
                lines.append(f"   Error: {transition.result.error}")

        return "\n".join(lines)

    def __len__(self) -> int:
        """Number of transitions recorded."""
        return len(self.history)

    def __repr__(self) -> str:
        success_count = sum(1 for t in self.history if t.result.success)
        return (
            f"WorkingMemory({len(self.history)} transitions, "
            f"{success_count} successful)"
        )


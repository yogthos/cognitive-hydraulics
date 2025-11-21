"""Unit tests for WorkingMemory."""

from datetime import datetime

import pytest

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.working_memory import WorkingMemory, StateTransition

# Rebuild OperatorResult to resolve forward references
OperatorResult.model_rebuild()


class DummyOperator(Operator):
    """Dummy operator for testing."""

    def __init__(self, name: str = "dummy"):
        super().__init__(name, is_destructive=False)

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        return True

    async def execute(self, state: EditorState) -> OperatorResult:
        return OperatorResult(success=True, output="Dummy executed")


class TestWorkingMemory:
    """Tests for WorkingMemory."""

    def test_create_working_memory(self):
        """Test creating a WorkingMemory instance."""
        state = EditorState()
        goal = Goal(description="Test goal")

        wm = WorkingMemory(state, goal)

        assert wm.current_state == state
        assert wm.current_goal == goal
        assert len(wm) == 0  # No transitions yet

    def test_record_successful_transition(self):
        """Test recording a successful state transition."""
        state1 = EditorState(working_directory="/project")
        state2 = EditorState(working_directory="/project", last_output="Done")
        goal = Goal(description="Test")

        wm = WorkingMemory(state1, goal)
        operator = DummyOperator("test_op")
        result = OperatorResult(success=True, output="Success")

        wm.record_transition(operator, result, state2, goal)

        assert len(wm) == 1
        assert wm.current_state == state2
        assert wm.current_state.last_output == "Done"

    def test_record_failed_transition(self):
        """Test recording a failed transition."""
        state = EditorState()
        goal = Goal(description="Test")

        wm = WorkingMemory(state, goal)
        operator = DummyOperator("failing_op")
        result = OperatorResult(success=False, output="", error="Operation failed")

        wm.record_transition(operator, result, state, goal)

        assert len(wm) == 1
        failed = wm.get_failed_operators()
        assert "failing_op" in failed

    def test_get_recent_transitions(self):
        """Test retrieving recent transitions."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        # Record 5 transitions
        for i in range(5):
            op = DummyOperator(f"op_{i}")
            result = OperatorResult(success=True, output=f"Result {i}")
            wm.record_transition(op, result, state, goal)

        recent = wm.get_recent_transitions(n=3)
        assert len(recent) == 3
        assert recent[-1].operator == "op_4"  # Most recent

    def test_detect_loop(self):
        """Test loop detection."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        # Same operator fails 3 times
        failing_op = DummyOperator("repeated_fail")
        for _ in range(3):
            result = OperatorResult(success=False, output="", error="Failed")
            wm.record_transition(failing_op, result, state, goal)

        assert wm.has_loop()

    def test_no_loop_with_different_operators(self):
        """Test that different operators don't trigger loop detection."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        # Different operators fail
        for i in range(3):
            op = DummyOperator(f"op_{i}")
            result = OperatorResult(success=False, output="", error="Failed")
            wm.record_transition(op, result, state, goal)

        assert not wm.has_loop()

    def test_no_loop_with_successes(self):
        """Test that successful operations don't count toward loops."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        op = DummyOperator("test_op")
        # Mix of success and failure
        for success in [True, False, True, False]:
            result = OperatorResult(success=success, output="", error=None if success else "Fail")
            wm.record_transition(op, result, state, goal)

        assert not wm.has_loop()

    def test_rollback(self):
        """Test rolling back to previous state."""
        state1 = EditorState(working_directory="/v1")
        state2 = EditorState(working_directory="/v2")
        state3 = EditorState(working_directory="/v3")
        goal = Goal(description="Test")

        wm = WorkingMemory(state1, goal)

        op = DummyOperator()
        result = OperatorResult(success=True, output="Step 1")
        wm.record_transition(op, result, state2, goal)

        result2 = OperatorResult(success=True, output="Step 2")
        wm.record_transition(op, result2, state3, goal)

        assert wm.current_state.working_directory == "/v3"

        # Rollback 1 step
        prev_state = wm.rollback(steps=1)
        assert prev_state.working_directory == "/v2"

        # Rollback 2 steps (to initial)
        initial_state = wm.rollback(steps=2)
        assert initial_state.working_directory == "/v1"

    def test_rollback_beyond_history(self):
        """Test rollback when requesting more steps than history."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        # Try to rollback when no history exists
        rolled_back = wm.rollback(steps=10)
        assert rolled_back == state  # Returns initial state

    def test_get_trace(self):
        """Test generating a trace of transitions."""
        state = EditorState(working_directory="/project")
        goal = Goal(description="Fix bug")
        wm = WorkingMemory(state, goal)

        # Record some transitions
        op1 = DummyOperator("read_file")
        result1 = OperatorResult(success=True, output="File read")
        wm.record_transition(op1, result1, state, goal)

        op2 = DummyOperator("edit_file")
        result2 = OperatorResult(success=False, output="", error="Permission denied")
        wm.record_transition(op2, result2, state, goal)

        trace = wm.get_trace()

        assert "Fix bug" in trace
        assert "read_file" in trace
        assert "edit_file" in trace
        assert "Permission denied" in trace
        assert "✓" in trace  # Success symbol
        assert "✗" in trace  # Failure symbol

    def test_history_size_limit(self):
        """Test that history is trimmed when exceeding max size."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)
        wm.max_history_size = 10  # Set small limit for testing

        # Record more transitions than the limit
        op = DummyOperator()
        for i in range(15):
            result = OperatorResult(success=True, output=f"Step {i}")
            wm.record_transition(op, result, state, goal)

        # Should be trimmed to max_history_size
        assert len(wm) == 10
        # Should keep the most recent ones
        assert wm.history[-1].result.output == "Step 14"

    def test_repr(self):
        """Test string representation."""
        state = EditorState()
        goal = Goal(description="Test")
        wm = WorkingMemory(state, goal)

        # Add some transitions
        op = DummyOperator()
        result_success = OperatorResult(success=True, output="OK")
        result_fail = OperatorResult(success=False, output="", error="Fail")

        wm.record_transition(op, result_success, state, goal)
        wm.record_transition(op, result_fail, state, goal)

        repr_str = repr(wm)
        assert "2 transitions" in repr_str
        assert "1 successful" in repr_str


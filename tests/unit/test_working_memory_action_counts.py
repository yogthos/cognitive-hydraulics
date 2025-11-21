"""Unit tests for WorkingMemory action count tracking."""

import pytest
from cognitive_hydraulics.core.working_memory import WorkingMemory
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.operators.file_ops import OpReadFile


class TestWorkingMemoryActionCounts:
    """Test action count tracking in WorkingMemory."""

    def test_action_count_initial_zero(self):
        """Test that action counts start at zero."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")
        wm = WorkingMemory(state, goal)

        assert wm.get_action_count("read_file") == 0
        assert wm.get_action_count("nonexistent_op") == 0

    def test_action_count_increments(self):
        """Test that action counts increment when operators are executed."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")
        wm = WorkingMemory(state, goal)

        op = OpReadFile("test.py")
        result = OperatorResult(success=True, new_state=state, output="ok")

        # Execute operator multiple times
        wm.record_transition(op, result, state, goal)
        assert wm.get_action_count("read_file(test.py)") == 1

        wm.record_transition(op, result, state, goal)
        assert wm.get_action_count("read_file(test.py)") == 2

        wm.record_transition(op, result, state, goal)
        assert wm.get_action_count("read_file(test.py)") == 3

    def test_action_count_multiple_operators(self):
        """Test that different operators have separate counts."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")
        wm = WorkingMemory(state, goal)

        op1 = OpReadFile("file1.py")
        op2 = OpReadFile("file2.py")
        result = OperatorResult(success=True, new_state=state, output="ok")

        wm.record_transition(op1, result, state, goal)
        wm.record_transition(op1, result, state, goal)
        wm.record_transition(op2, result, state, goal)

        assert wm.get_action_count("read_file(file1.py)") == 2
        assert wm.get_action_count("read_file(file2.py)") == 1

    def test_reset_action_counts(self):
        """Test that action counts can be reset."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")
        wm = WorkingMemory(state, goal)

        op = OpReadFile("test.py")
        result = OperatorResult(success=True, new_state=state, output="ok")

        wm.record_transition(op, result, state, goal)
        wm.record_transition(op, result, state, goal)
        assert wm.get_action_count("read_file(test.py)") == 2

        wm.reset_action_counts()
        assert wm.get_action_count("read_file(test.py)") == 0


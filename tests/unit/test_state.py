"""Unit tests for State models."""

from datetime import datetime

import pytest

from cognitive_hydraulics.core.state import EditorState, FileContent, Goal


class TestFileContent:
    """Tests for FileContent model."""

    def test_create_file_content(self):
        """Test creating a FileContent instance."""
        content = FileContent(
            path="/test/file.py",
            content="print('hello')",
            language="python",
            last_modified=datetime.now(),
        )

        assert content.path == "/test/file.py"
        assert content.language == "python"
        assert content.tree_sitter_tree is None  # Not parsed yet

    def test_file_content_with_tree(self):
        """Test FileContent with parsed tree."""
        tree = {"type": "module", "children": []}
        content = FileContent(
            path="/test/file.py",
            content="x = 1",
            language="python",
            tree_sitter_tree=tree,
            last_modified=datetime.now(),
        )

        assert content.tree_sitter_tree == tree


class TestEditorState:
    """Tests for EditorState model."""

    def test_create_empty_state(self):
        """Test creating an empty EditorState."""
        state = EditorState()

        assert state.working_directory == "."
        assert len(state.open_files) == 0
        assert len(state.error_log) == 0
        assert state.last_output is None

    def test_state_with_files(self):
        """Test EditorState with open files."""
        file1 = FileContent(
            path="a.py", content="x=1", language="python", last_modified=datetime.now()
        )
        file2 = FileContent(
            path="b.py", content="y=2", language="python", last_modified=datetime.now()
        )

        state = EditorState(
            working_directory="/project",
            open_files={"a.py": file1, "b.py": file2},
        )

        assert len(state.open_files) == 2
        assert "a.py" in state.open_files
        assert state.open_files["a.py"].content == "x=1"

    def test_compress_for_llm(self):
        """Test context compression for LLM."""
        state = EditorState(
            working_directory="/project",
            error_log=["Error 1", "Error 2", "Error 3", "Error 4"],
            last_output="Test output",
        )

        compressed = state.compress_for_llm()

        assert compressed["working_directory"] == "/project"
        assert compressed["last_output"] == "Test output"
        # Should only include last 3 errors
        assert len(compressed["recent_errors"]) == 3
        assert compressed["recent_errors"] == ["Error 2", "Error 3", "Error 4"]

    def test_state_with_cursor_position(self):
        """Test EditorState with cursor positions."""
        state = EditorState(
            cursor_position={"main.py": 42, "test.py": 10}
        )

        assert state.cursor_position["main.py"] == 42
        assert state.cursor_position["test.py"] == 10


class TestGoal:
    """Tests for Goal model."""

    def test_create_simple_goal(self):
        """Test creating a simple goal."""
        goal = Goal(description="Fix the bug in main.py")

        assert goal.description == "Fix the bug in main.py"
        assert goal.status == "active"
        assert goal.priority == 1.0
        assert len(goal.sub_goals) == 0
        assert goal.parent_goal is None

    def test_goal_depth_no_parent(self):
        """Test goal depth calculation with no parent."""
        goal = Goal(description="Top level goal")

        assert goal.depth() == 0

    def test_goal_depth_with_hierarchy(self):
        """Test goal depth calculation with parent hierarchy."""
        parent = Goal(description="Parent goal")
        child = Goal(description="Child goal", parent_goal=parent)
        grandchild = Goal(description="Grandchild goal", parent_goal=child)

        assert parent.depth() == 0
        assert child.depth() == 1
        assert grandchild.depth() == 2

    def test_goal_with_subgoals(self):
        """Test goal with sub-goals."""
        parent = Goal(description="Main goal")
        sub1 = Goal(description="Subgoal 1", parent_goal=parent)
        sub2 = Goal(description="Subgoal 2", parent_goal=parent)

        parent.sub_goals.append(sub1)
        parent.sub_goals.append(sub2)

        assert len(parent.sub_goals) == 2
        assert parent.sub_goals[0].description == "Subgoal 1"

    def test_goal_status_transitions(self):
        """Test goal status changes."""
        goal = Goal(description="Test goal")

        assert goal.status == "active"

        goal.status = "success"
        assert goal.status == "success"

        goal.status = "failure"
        assert goal.status == "failure"

    def test_goal_priority(self):
        """Test goal priority values."""
        low_priority = Goal(description="Low", priority=0.5)
        high_priority = Goal(description="High", priority=2.0)

        assert low_priority.priority < high_priority.priority

    def test_goal_serialization(self):
        """Test that goals can be serialized to dict."""
        goal = Goal(
            description="Test goal",
            status="active",
            priority=1.5,
        )

        goal_dict = goal.model_dump()

        assert goal_dict["description"] == "Test goal"
        assert goal_dict["status"] == "active"
        assert goal_dict["priority"] == 1.5


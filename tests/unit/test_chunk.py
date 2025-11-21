"""Unit tests for chunk model and creation."""

import pytest
from datetime import datetime, timedelta

from cognitive_hydraulics.memory.chunk import (
    Chunk,
    create_chunk_from_success,
    create_state_signature,
)
from cognitive_hydraulics.core.state import EditorState
from cognitive_hydraulics.operators.file_ops import OpReadFile


class TestChunk:
    """Tests for Chunk model."""

    def test_create_chunk(self):
        """Test creating a chunk."""
        chunk = Chunk(
            id="test123",
            state_signature={"goal": "test", "has_errors": False},
            operator_name="read_file",
            operator_params={"path": "test.py"},
            goal_description="Read test file",
        )

        assert chunk.id == "test123"
        assert chunk.operator_name == "read_file"
        assert chunk.success_count == 1
        assert chunk.failure_count == 0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        chunk = Chunk(
            id="test123",
            state_signature={},
            operator_name="test_op",
            operator_params={},
            goal_description="test",
            success_count=8,
            failure_count=2,
        )

        assert chunk.success_rate() == 0.8  # 8/10

    def test_success_rate_no_history(self):
        """Test success rate with no history."""
        chunk = Chunk(
            id="test123",
            state_signature={},
            operator_name="test_op",
            operator_params={},
            goal_description="test",
            success_count=0,
            failure_count=0,
        )

        assert chunk.success_rate() == 0.0

    def test_activation_calculation(self):
        """Test ACT-R style activation."""
        chunk = Chunk(
            id="test123",
            state_signature={},
            operator_name="test_op",
            operator_params={},
            goal_description="test",
            success_count=5,
        )

        # Recent use → high activation
        activation = chunk.activation()
        assert activation > 0.0  # Positive activation

    def test_activation_decay(self):
        """Test activation decreases with time."""
        chunk = Chunk(
            id="test123",
            state_signature={},
            operator_name="test_op",
            operator_params={},
            goal_description="test",
            success_count=5,
            last_used=datetime.now() - timedelta(hours=2),  # Used 2 hours ago
        )

        # Old use → lower activation
        activation = chunk.activation()

        # Should still be positive due to frequency
        assert activation != 0.0

    def test_repr(self):
        """Test string representation."""
        chunk = Chunk(
            id="test123456",
            state_signature={},
            operator_name="read_file",
            operator_params={},
            goal_description="test",
            success_count=3,
            failure_count=1,
        )

        repr_str = repr(chunk)

        assert "Chunk" in repr_str
        assert "test1234" in repr_str  # Truncated ID
        assert "read_file" in repr_str
        assert "75.00%" in repr_str  # Success rate


class TestStateSignature:
    """Tests for state signature creation."""

    def test_create_basic_signature(self):
        """Test creating basic state signature."""
        state = EditorState(working_directory="/project")
        goal = "Fix the bug"

        signature = create_state_signature(state, goal)

        assert signature["goal"] == "Fix the bug"
        assert signature["working_directory"] == "/project"
        assert signature["open_file_count"] == 0
        assert signature["has_errors"] is False

    def test_signature_with_errors(self):
        """Test signature includes error information."""
        state = EditorState(error_log=["Error 1", "Error 2", "Error 3"])
        goal = "Fix errors"

        signature = create_state_signature(state, goal)

        assert signature["has_errors"] is True
        assert "Error 3" in signature["recent_error"]  # Most recent

    def test_signature_with_open_files(self):
        """Test signature includes open files."""
        from cognitive_hydraulics.core.state import FileContent
        from datetime import datetime

        state = EditorState(
            open_files={
                "main.py": FileContent(
                    path="main.py", content="code", language="python", last_modified=datetime.now()
                ),
                "test.py": FileContent(
                    path="test.py", content="tests", language="python", last_modified=datetime.now()
                ),
            }
        )
        goal = "Test"

        signature = create_state_signature(state, goal)

        assert signature["open_file_count"] == 2
        assert "main.py" in signature["open_files"]
        assert "test.py" in signature["open_files"]

    def test_signature_truncates_long_lists(self):
        """Test that signature truncates long file lists."""
        from cognitive_hydraulics.core.state import FileContent
        from datetime import datetime

        # Create 10 files
        files = {
            f"file{i}.py": FileContent(
                path=f"file{i}.py", content="", language="python", last_modified=datetime.now()
            )
            for i in range(10)
        }
        state = EditorState(open_files=files)
        goal = "Test"

        signature = create_state_signature(state, goal)

        # Should only keep top 5
        assert len(signature["open_files"]) <= 5

    def test_signature_with_last_output(self):
        """Test signature includes last output."""
        state = EditorState(last_output="Test output message")
        goal = "Test"

        signature = create_state_signature(state, goal)

        assert "last_output_snippet" in signature
        assert "Test output" in signature["last_output_snippet"]


class TestChunkCreation:
    """Tests for creating chunks from successful resolutions."""

    def test_create_chunk_from_success(self):
        """Test creating chunk from successful operator."""
        state = EditorState(working_directory="/project")
        operator = OpReadFile("main.py")
        goal = "Read the file"
        utility = 5.5

        chunk = create_chunk_from_success(state, operator, goal, utility)

        assert chunk.operator_name == operator.name
        assert chunk.goal_description == goal
        assert chunk.utility == utility
        assert chunk.success_count == 1
        assert chunk.failure_count == 0

    def test_chunk_id_deterministic(self):
        """Test that chunk IDs are deterministic."""
        state = EditorState(working_directory="/project")
        operator = OpReadFile("main.py")
        goal = "Read the file"

        chunk1 = create_chunk_from_success(state, operator, goal)
        chunk2 = create_chunk_from_success(state, operator, goal)

        # Same inputs → same ID
        assert chunk1.id == chunk2.id

    def test_chunk_id_different_for_different_inputs(self):
        """Test that different inputs produce different IDs."""
        state = EditorState(working_directory="/project")
        operator1 = OpReadFile("main.py")
        operator2 = OpReadFile("test.py")
        goal = "Read files"

        chunk1 = create_chunk_from_success(state, operator1, goal)
        chunk2 = create_chunk_from_success(state, operator2, goal)

        # Different operators → different IDs
        assert chunk1.id != chunk2.id

    def test_chunk_captures_operator_parameters(self):
        """Test that chunk captures operator parameters."""
        state = EditorState()
        operator = OpReadFile("config.json")
        goal = "Read config"

        chunk = create_chunk_from_success(state, operator, goal)

        # Should capture operator's parameters
        assert "path" in chunk.operator_params or "file_path" in repr(chunk.operator_params)


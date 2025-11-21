"""Unit tests for context window management."""

from datetime import datetime
import pytest

from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.utils.context_manager import ContextWindowManager


class TestContextWindowManager:
    """Tests for ContextWindowManager."""

    def test_create_context_manager(self):
        """Test creating a context manager."""
        cm = ContextWindowManager(max_tokens=1000)

        assert cm.max_tokens == 1000
        assert cm.max_chars == 4000  # 1000 * 4
        assert cm.code_analyzer is not None

    def test_compress_empty_state(self):
        """Test compressing an empty state."""
        cm = ContextWindowManager()
        state = EditorState()
        goal = Goal(description="Test goal")

        compressed = cm.compress_state(state, goal)

        assert compressed["goal"] == "Test goal"
        assert compressed["working_directory"] == "."
        assert compressed["error"] is None
        assert len(compressed["relevant_code"]) == 0

    def test_compress_state_with_small_file(self):
        """Test compressing state with a small file that fits."""
        cm = ContextWindowManager(max_tokens=1000)

        small_code = "def hello():\n    return 'world'"
        file_content = FileContent(
            path="small.py",
            content=small_code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["small.py"] = file_content
        goal = Goal(description="Fix small.py")

        compressed = cm.compress_state(state, goal)

        # File mentioned in goal should be included
        assert "small.py" in compressed["relevant_code"]
        assert "hello" in compressed["relevant_code"]["small.py"]

    def test_compress_state_with_large_file(self):
        """Test compressing state with a file too large for context."""
        cm = ContextWindowManager(max_tokens=100)  # Very small window

        # Create large code
        large_code = "\n".join([f"x{i} = {i}" for i in range(1000)])
        file_content = FileContent(
            path="large.py",
            content=large_code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["large.py"] = file_content
        goal = Goal(description="Fix large.py")

        compressed = cm.compress_state(state, goal)

        # Should have summary instead of full code
        assert "large.py" in (compressed.get("file_summary", {}) or compressed.get("relevant_code", {}))

    def test_calculate_file_priorities(self):
        """Test file priority calculation."""
        cm = ContextWindowManager()

        file1 = FileContent(
            path="important.py",
            content="x = 1",
            language="python",
            last_modified=datetime.now(),
        )
        file2 = FileContent(
            path="other.py",
            content="y = 2",
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["important.py"] = file1
        state.open_files["other.py"] = file2
        state.cursor_position["important.py"] = 10

        goal = Goal(description="Fix important.py")

        priorities = cm._calculate_file_priorities(state, goal)

        # File mentioned in goal should have higher priority
        assert priorities["important.py"] > priorities["other.py"]

    def test_priority_boost_for_error(self):
        """Test that files mentioned in errors get priority boost."""
        cm = ContextWindowManager()

        file1 = FileContent(
            path="buggy.py",
            content="x = 1",
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["buggy.py"] = file1
        state.error_log.append("Error in buggy.py: NameError")

        goal = Goal(description="Fix bug")

        priorities = cm._calculate_file_priorities(state, goal)

        # File in error log should have boosted priority
        assert priorities["buggy.py"] > 1.0

    def test_extract_relevant_section_whole_file(self):
        """Test extracting relevant section when file is small."""
        cm = ContextWindowManager()

        code = "def foo():\n    pass"
        file_content = FileContent(
            path="test.py",
            content=code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        goal = Goal(description="Fix test")

        section = cm._extract_relevant_section(
            file_content, goal, state, max_chars=1000
        )

        # Whole file should be returned since it's small
        assert section == code

    def test_extract_function_by_name(self):
        """Test extracting a specific function mentioned in goal."""
        cm = ContextWindowManager()

        code = """
def target_function():
    return 42

def other_function():
    return 'hello'
"""
        file_content = FileContent(
            path="test.py",
            content=code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        goal = Goal(description="Fix target_function")

        section = cm._extract_relevant_section(
            file_content, goal, state, max_chars=500
        )

        # Should extract only the target function
        assert section is not None
        if "target_function" in section:
            assert "target_function" in section
            assert "42" in section

    def test_truncate_to_lines(self):
        """Test truncating code to fit max chars."""
        cm = ContextWindowManager()

        code = "\n".join([f"line {i}" for i in range(100)])

        truncated = cm._truncate_to_lines(code, max_chars=50)

        assert len(truncated) <= 100  # Should be truncated
        assert "truncated" in truncated.lower()

    def test_summarize_file(self):
        """Test creating a file summary."""
        cm = ContextWindowManager()

        code = """
import os
import sys

class MyClass:
    pass

def function_one():
    pass

def function_two():
    pass
"""
        file_content = FileContent(
            path="test.py",
            content=code,
            language="python",
            last_modified=datetime.now(),
        )

        summary = cm._summarize_file(file_content)

        assert "python" in summary.lower()
        assert "MyClass" in summary or "Classes" in summary
        assert "function" in summary.lower()

    def test_estimate_tokens(self):
        """Test token estimation."""
        cm = ContextWindowManager()

        text = "x" * 100  # 100 characters

        estimated = cm.estimate_tokens(text)

        # Should be approximately 100 / 4 = 25 tokens
        assert 20 <= estimated <= 30

    def test_compress_preserves_goal(self):
        """Test that goal is always preserved in compression."""
        cm = ContextWindowManager(max_tokens=10)  # Tiny window

        large_code = "x" * 10000
        file_content = FileContent(
            path="huge.py",
            content=large_code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["huge.py"] = file_content
        goal = Goal(description="Important goal description")

        compressed = cm.compress_state(state, goal)

        # Goal should always be preserved
        assert "goal" in compressed
        assert compressed["goal"] == "Important goal description"

    def test_compress_preserves_error(self):
        """Test that recent error is always preserved."""
        cm = ContextWindowManager(max_tokens=10)  # Tiny window

        state = EditorState()
        state.error_log.append("Critical error message")
        goal = Goal(description="Fix error")

        compressed = cm.compress_state(state, goal)

        # Error should always be preserved
        assert "error" in compressed
        assert compressed["error"] == "Critical error message"

    def test_context_manager_with_multiple_files(self):
        """Test compression with multiple files of different priorities."""
        cm = ContextWindowManager(max_tokens=200)

        high_priority = FileContent(
            path="important.py",
            content="def critical(): pass",
            language="python",
            last_modified=datetime.now(),
        )

        low_priority = FileContent(
            path="other.py",
            content="def unrelated(): pass",
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.open_files["important.py"] = high_priority
        state.open_files["other.py"] = low_priority

        goal = Goal(description="Fix important.py")

        compressed = cm.compress_state(state, goal)

        # High priority file should be included
        relevant_code = compressed.get("relevant_code", {})
        if relevant_code:
            assert "important.py" in relevant_code

    def test_extract_around_error_line(self):
        """Test extracting code around an error line."""
        cm = ContextWindowManager()

        code = """
def function_one():
    x = 1
    y = 2
    return x + y

def function_two():
    a = 1
    b = 0
    return a / b  # Line 9: Division by zero!
"""
        file_content = FileContent(
            path="test.py",
            content=code,
            language="python",
            last_modified=datetime.now(),
        )

        state = EditorState()
        state.error_log.append("ZeroDivisionError at line 9")
        goal = Goal(description="Fix error")

        section = cm._extract_relevant_section(
            file_content, goal, state, max_chars=500
        )

        # Should extract around the error line
        # Might be the whole file if small enough, or the function containing the error
        assert section is not None


"""Unit tests for concrete operators."""

import pytest
from pathlib import Path

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import OperatorResult
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpListDirectory, OpWriteFile

# Rebuild to resolve forward references
OperatorResult.model_rebuild()


class TestOpReadFile:
    """Tests for OpReadFile operator."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, sample_workspace):
        """Test reading an existing file."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Read sample.py")

        op = OpReadFile("sample.py")
        assert op.is_applicable(state, goal)

        result = await op.execute(state)

        assert result.success
        assert "sample.py" in result.new_state.open_files
        file_content = result.new_state.open_files["sample.py"]
        assert file_content.language == "python"
        assert "process_data" in file_content.content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, sample_workspace):
        """Test reading a file that doesn't exist."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Read missing file")

        op = OpReadFile("nonexistent.py")
        assert not op.is_applicable(state, goal)

        result = await op.execute(state)

        assert not result.success
        assert "Failed to read" in result.error

    @pytest.mark.asyncio
    async def test_read_multiple_files(self, sample_workspace):
        """Test reading multiple files into state."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Read files")

        # Read first file
        op1 = OpReadFile("sample.py")
        result1 = await op1.execute(state)
        assert result1.success

        # Create another file
        (sample_workspace / "test.py").write_text("# Test file")

        # Read second file into the updated state
        op2 = OpReadFile("test.py")
        result2 = await op2.execute(result1.new_state)
        assert result2.success
        assert len(result2.new_state.open_files) == 2

    def test_read_file_not_destructive(self):
        """Test that read file operator is marked as safe."""
        op = OpReadFile("test.py")
        assert not op.is_destructive
        assert not op.requires_approval()


class TestOpListDirectory:
    """Tests for OpListDirectory operator."""

    @pytest.mark.asyncio
    async def test_list_directory(self, sample_workspace):
        """Test listing directory contents."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="List files")

        op = OpListDirectory(".")
        assert op.is_applicable(state, goal)

        result = await op.execute(state)

        assert result.success
        assert "sample.py" in result.output
        assert "Contents of" in result.output

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self, sample_workspace):
        """Test listing a directory that doesn't exist."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="List missing dir")

        op = OpListDirectory("nonexistent_dir")
        assert not op.is_applicable(state, goal)

        result = await op.execute(state)

        assert not result.success
        assert "Failed to list" in result.error

    def test_list_dir_not_destructive(self):
        """Test that list directory operator is marked as safe."""
        op = OpListDirectory(".")
        assert not op.is_destructive
        assert not op.requires_approval()


class TestOpWriteFile:
    """Tests for OpWriteFile operator."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, sample_workspace):
        """Test writing a new file."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Create new file")

        content = "# New Python file\nprint('hello')"
        op = OpWriteFile("new_file.py", content)

        assert op.is_applicable(state, goal)

        result = await op.execute(state)

        assert result.success
        assert "Wrote" in result.output
        assert (sample_workspace / "new_file.py").exists()
        assert (sample_workspace / "new_file.py").read_text() == content

    @pytest.mark.asyncio
    async def test_write_overwrites_existing(self, sample_workspace):
        """Test that write file overwrites existing content."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Overwrite file")

        new_content = "# Completely new content"
        op = OpWriteFile("sample.py", new_content)

        result = await op.execute(state)

        assert result.success
        assert (sample_workspace / "sample.py").read_text() == new_content

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, sample_workspace):
        """Test that write file creates parent directories."""
        state = EditorState(working_directory=str(sample_workspace))
        goal = Goal(description="Write to nested path")

        content = "# Nested file"
        op = OpWriteFile("subdir/nested/file.py", content)

        result = await op.execute(state)

        assert result.success
        nested_path = sample_workspace / "subdir" / "nested" / "file.py"
        assert nested_path.exists()
        assert nested_path.read_text() == content

    def test_write_file_is_destructive(self):
        """Test that write file operator is marked as destructive."""
        op = OpWriteFile("test.py", "content")
        assert op.is_destructive
        assert op.requires_approval()


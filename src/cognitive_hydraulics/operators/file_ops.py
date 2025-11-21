"""File operation operators (read, write, list)."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent

# Rebuild models to resolve forward references
EditorState.model_rebuild()
OperatorResult.model_rebuild()


class OpReadFile(Operator):
    """Read a file from the filesystem (safe, non-destructive)."""

    def __init__(self, path: str):
        super().__init__(name=f"read_file({path})", is_destructive=False)
        self.path = path

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        """Can only read files that exist."""
        full_path = Path(state.working_directory) / self.path
        return full_path.exists() and full_path.is_file()

    async def execute(self, state: EditorState) -> OperatorResult:
        """Read the file and add it to open_files."""
        try:
            full_path = Path(state.working_directory) / self.path
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Detect language from extension
            ext = full_path.suffix.lstrip(".")
            language_map = {
                "py": "python",
                "js": "javascript",
                "ts": "typescript",
                "rs": "rust",
                "go": "go",
                "java": "java",
                "c": "c",
                "cpp": "cpp",
                "h": "c",
                "hpp": "cpp",
            }
            language = language_map.get(ext, "text")

            # Create new state with file added
            new_state = state.model_copy(deep=True)
            new_state.open_files[str(self.path)] = FileContent(
                path=str(self.path),
                content=content,
                language=language,
                tree_sitter_tree=None,  # Will be parsed later by tree-sitter
                last_modified=datetime.fromtimestamp(full_path.stat().st_mtime),
            )

            return OperatorResult(
                success=True,
                new_state=new_state,
                output=f"Read {len(content)} bytes from {self.path}",
            )

        except Exception as e:
            return OperatorResult(
                success=False,
                output="",
                error=f"Failed to read {self.path}: {str(e)}",
            )


class OpListDirectory(Operator):
    """List files in a directory (safe, non-destructive)."""

    def __init__(self, path: str = "."):
        super().__init__(name=f"list_dir({path})", is_destructive=False)
        self.path = path

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        """Can only list directories that exist."""
        full_path = Path(state.working_directory) / self.path
        return full_path.exists() and full_path.is_dir()

    async def execute(self, state: EditorState) -> OperatorResult:
        """List directory contents."""
        try:
            full_path = Path(state.working_directory) / self.path
            entries = list(full_path.iterdir())

            # Format output
            files = [e.name for e in entries if e.is_file()]
            dirs = [e.name + "/" for e in entries if e.is_dir()]
            all_entries = sorted(dirs) + sorted(files)

            output = f"Contents of {self.path}:\n" + "\n".join(all_entries)

            # Update state with output
            new_state = state.model_copy(deep=True)
            new_state.last_output = output

            return OperatorResult(
                success=True,
                new_state=new_state,
                output=output,
            )

        except Exception as e:
            return OperatorResult(
                success=False,
                output="",
                error=f"Failed to list {self.path}: {str(e)}",
            )


class OpWriteFile(Operator):
    """Write content to a file (DESTRUCTIVE - requires approval)."""

    def __init__(self, path: str, content: str):
        super().__init__(name=f"write_file({path})", is_destructive=True)
        self.path = path
        self.content = content

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        """Always applicable (but requires approval)."""
        return True

    async def execute(self, state: EditorState) -> OperatorResult:
        """Write content to file."""
        try:
            full_path = Path(state.working_directory) / self.path

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(self.content)

            # Update state
            new_state = state.model_copy(deep=True)
            new_state.last_output = f"Wrote {len(self.content)} bytes to {self.path}"

            return OperatorResult(
                success=True,
                new_state=new_state,
                output=f"Wrote {len(self.content)} bytes to {self.path}",
            )

        except Exception as e:
            return OperatorResult(
                success=False,
                output="",
                error=f"Failed to write {self.path}: {str(e)}",
            )


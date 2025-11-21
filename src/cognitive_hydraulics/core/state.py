"""State management for the cognitive architecture."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class FileContent(BaseModel):
    """Represents a file with parsed structure."""

    path: str
    content: str
    language: str
    tree_sitter_tree: Optional[dict] = None  # Serialized AST
    last_modified: datetime


class EditorState(BaseModel):
    """Current state of the development environment."""

    open_files: Dict[str, FileContent] = Field(default_factory=dict)
    cursor_position: Dict[str, int] = Field(default_factory=dict)
    last_output: Optional[str] = None
    error_log: List[str] = Field(default_factory=list)
    git_status: Optional[str] = None
    working_directory: str = "."

    def compress_for_llm(self, goal: Optional[Goal] = None) -> dict:
        """
        Return a context-window-friendly version.

        If goal is provided, uses intelligent compression with tree-sitter.
        Otherwise, returns a basic compression.
        """
        if goal:
            # Use intelligent compression with context manager
            try:
                from cognitive_hydraulics.utils.context_manager import ContextWindowManager
                cm = ContextWindowManager()
                return cm.compress_state(self, goal)
            except ImportError:
                pass  # Fall back to basic compression

        # Basic compression
        return {
            "working_directory": self.working_directory,
            "open_files": list(self.open_files.keys()),
            "last_output": self.last_output,
            "recent_errors": self.error_log[-3:] if self.error_log else [],
        }


class Goal(BaseModel):
    """Represents a goal or sub-goal."""

    description: str
    parent_goal: Optional[Goal] = None
    sub_goals: List[Goal] = Field(default_factory=list)
    status: str = "active"  # active, success, failure
    priority: float = 1.0

    def depth(self) -> int:
        """Calculate nesting depth."""
        if self.parent_goal is None:
            return 0
        return 1 + self.parent_goal.depth()


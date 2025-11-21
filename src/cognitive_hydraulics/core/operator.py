"""Base operator class for all actions in the cognitive architecture."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from cognitive_hydraulics.core.state import EditorState, Goal


class OperatorResult(BaseModel):
    """Result of executing an operator."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    new_state: Optional[EditorState] = None
    output: str
    error: Optional[str] = None


class Operator(ABC):
    """Base class for all operators."""

    def __init__(self, name: str, is_destructive: bool = False) -> None:
        self.name = name
        self.is_destructive = is_destructive

    @abstractmethod
    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        """Can this operator be applied in the current state?"""
        pass

    @abstractmethod
    async def execute(self, state: EditorState) -> OperatorResult:
        """Execute the operator."""
        pass

    def requires_approval(self) -> bool:
        """Should this require human approval?"""
        return self.is_destructive

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"


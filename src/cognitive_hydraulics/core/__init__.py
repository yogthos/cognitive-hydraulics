"""Core data structures for the cognitive architecture."""

from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.working_memory import WorkingMemory, StateTransition

__all__ = [
    "EditorState",
    "Goal",
    "FileContent",
    "Operator",
    "OperatorResult",
    "WorkingMemory",
    "StateTransition",
]


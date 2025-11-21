"""
Cognitive Hydraulics - A Hybrid Neuro-Symbolic Reasoning Engine

This package implements a cognitive architecture that combines:
- Soar (symbolic reasoning) as the default System 2
- ACT-R (utility-based selection) as the fallback System 1
- Local LLM as the intuition engine for both systems
"""

__version__ = "0.1.0"

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator, OperatorResult

__all__ = [
    "EditorState",
    "Goal",
    "Operator",
    "OperatorResult",
]


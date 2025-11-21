"""Chunk model and chunking system for learning from experience."""

from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from cognitive_hydraulics.core.state import EditorState
from cognitive_hydraulics.core.operator import Operator


class Chunk(BaseModel):
    """
    A learned chunk representing a successful (State, Operator) pair.

    Chunks are created when ACT-R successfully resolves an impasse.
    They represent "compiled knowledge" - moving from slow deliberation
    to fast, automatic execution (declarative → procedural memory).
    """

    model_config = {"arbitrary_types_allowed": True}

    # Identifying information
    id: str = Field(description="Unique chunk ID")

    # The learned pattern
    state_signature: dict = Field(
        description="Compressed state representation (for matching)"
    )
    operator_name: str = Field(description="Name of the successful operator")
    operator_params: dict = Field(description="Parameters of the operator")

    # Context
    goal_description: str = Field(description="Goal this chunk solved")
    success_count: int = Field(default=1, description="Times this chunk succeeded")
    failure_count: int = Field(default=0, description="Times this chunk failed")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    last_used: datetime = Field(default_factory=datetime.now)
    utility: Optional[float] = Field(
        default=None, description="ACT-R utility when created"
    )

    def success_rate(self) -> float:
        """Calculate success rate of this chunk."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    def activation(self) -> float:
        """
        Calculate ACT-R style activation.

        Higher activation = more recently/frequently used.
        Formula: A = ln(success_count) - decay * time_since_use
        """
        import math

        if self.success_count == 0:
            return -float("inf")

        # Frequency component
        frequency = math.log(self.success_count + 1)  # +1 to avoid log(0)

        # Recency component (decay rate: 0.5 per hour)
        decay_rate = 0.5 / 3600  # per second
        time_since_use = (datetime.now() - self.last_used).total_seconds()
        recency_penalty = decay_rate * time_since_use

        return frequency - recency_penalty

    def __repr__(self) -> str:
        return (
            f"Chunk(id={self.id[:8]}..., op={self.operator_name}, "
            f"success_rate={self.success_rate():.2%}, "
            f"activation={self.activation():.2f})"
        )


def create_state_signature(state: EditorState, goal: str) -> dict:
    """
    Create a compressed signature for state matching.

    This should capture the "essence" of the state for similarity matching.

    Args:
        state: Current editor state
        goal: Goal description

    Returns:
        Dictionary signature for ChromaDB storage
    """
    signature = {
        "goal": goal,
        "working_directory": state.working_directory,
        "open_file_count": len(state.open_files),
        "has_errors": len(state.error_log) > 0,
    }

    # Add recent error if present
    if state.error_log:
        signature["recent_error"] = state.error_log[-1][:200]  # Truncate

    # Add file names (not content - too large)
    if state.open_files:
        signature["open_files"] = sorted(state.open_files.keys())[:5]  # Top 5

    # Add last output snippet
    if state.last_output:
        signature["last_output_snippet"] = state.last_output[:200]

    return signature


def create_chunk_from_success(
    state: EditorState,
    operator: Operator,
    goal: str,
    utility: Optional[float] = None,
) -> Chunk:
    """
    Create a chunk from a successful ACT-R resolution.

    Args:
        state: State when operator was selected
        operator: Operator that succeeded
        goal: Goal being pursued
        utility: ACT-R utility score

    Returns:
        New Chunk instance
    """
    import hashlib
    import json

    # Create signature
    signature = create_state_signature(state, goal)

    # Generate unique ID from signature + operator
    chunk_data = json.dumps(
        {**signature, "operator": operator.name}, sort_keys=True
    )
    chunk_id = hashlib.sha256(chunk_data.encode()).hexdigest()

    return Chunk(
        id=chunk_id,
        state_signature=signature,
        operator_name=operator.name,
        operator_params=operator.__dict__,  # Capture all operator params
        goal_description=goal,
        utility=utility,
    )


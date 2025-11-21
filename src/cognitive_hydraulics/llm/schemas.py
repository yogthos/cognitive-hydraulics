"""JSON schemas for structured LLM responses."""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class OperatorSuggestion(BaseModel):
    """Schema for a single operator suggestion from LLM."""

    name: str = Field(
        description="Operator name (e.g., 'read_file', 'search_codebase')"
    )
    parameters: dict = Field(
        description="Parameters for the operator (e.g., {'path': 'main.py'})"
    )
    reasoning: str = Field(
        description="Brief explanation of why this operator might work"
    )


class OperatorProposal(BaseModel):
    """Response schema for NO_CHANGE impasse (no operators available)."""

    operators: List[OperatorSuggestion] = Field(
        min_length=1,
        max_length=5,
        description="Suggested operators to try",
    )
    reasoning: str = Field(
        description="Overall reasoning for these suggestions"
    )


class UtilityEstimate(BaseModel):
    """Schema for ACT-R utility calculation for a single operator."""

    operator_name: str = Field(description="Name of the operator being evaluated")
    probability_of_success: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability this operator will advance toward the goal (0.0-1.0)",
    )
    estimated_cost: float = Field(
        ge=1.0,
        le=10.0,
        description="Estimated cost/effort of this operator (1=cheap, 10=expensive)",
    )
    reasoning: str = Field(
        description="Explanation for probability and cost estimates"
    )


class UtilityEvaluation(BaseModel):
    """Response schema for TIE impasse (multiple equal operators)."""

    evaluations: List[UtilityEstimate] = Field(
        min_length=1,
        description="Utility estimates for each operator",
    )
    recommendation: str = Field(
        description="Which operator is recommended and why"
    )


class CodeCandidate(BaseModel):
    """Schema for a code fix candidate in evolutionary solver."""

    hypothesis: str = Field(
        description="Description of the fix strategy (e.g., 'Decrease Range', 'Fix Loop Condition')"
    )
    code_patch: str = Field(
        description="The complete fixed code for the file"
    )
    reasoning: str = Field(
        description="Why this approach might work"
    )


class PopulationProposal(BaseModel):
    """Response schema for evolutionary population generation."""

    candidates: List[CodeCandidate] = Field(
        min_length=2,
        max_length=10,
        description="Distinct code fix candidates",
    )


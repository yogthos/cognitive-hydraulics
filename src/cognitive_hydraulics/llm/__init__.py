"""LLM integration with structured output and prompt templates."""

from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import (
    OperatorSuggestion,
    OperatorProposal,
    UtilityEstimate,
    UtilityEvaluation,
    CodeCandidate,
    PopulationProposal,
)
from cognitive_hydraulics.llm.prompts import PromptTemplates

__all__ = [
    "LLMClient",
    "OperatorSuggestion",
    "OperatorProposal",
    "UtilityEstimate",
    "UtilityEvaluation",
    "CodeCandidate",
    "PopulationProposal",
    "PromptTemplates",
]


"""ACT-R style conflict resolution using LLM for utility estimation."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import (
    UtilityEvaluation,
    UtilityEstimate,
    OperatorProposal,
    OperatorSuggestion,
)
from cognitive_hydraulics.llm.prompts import PromptTemplates
from cognitive_hydraulics.utils.context_manager import ContextWindowManager
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpListDirectory
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cognitive_hydraulics.config.settings import Config


class ACTRResolver:
    """
    ACT-R style conflict resolution using LLM for heuristic estimation.

    Implements the "System 1" fallback when Soar (System 2) fails.
    Uses LLM to estimate probability and cost, then calculates utility.

    Utility Formula: U = P * G - C + Noise
    - P: Probability of success (from LLM)
    - G: Goal value (configurable)
    - C: Cost (from LLM)
    - Noise: Random jitter for exploration
    """

    def __init__(
        self,
        goal_value: Optional[float] = None,
        noise_stddev: Optional[float] = None,
        model: Optional[str] = None,
        config: Optional["Config"] = None,
    ):
        """
        Initialize ACT-R resolver.

        Args:
            goal_value: Value G in utility equation (overrides config if provided)
            noise_stddev: Standard deviation for noise term (overrides config if provided)
            model: LLM model to use (overrides config if provided)
            config: Configuration object (if None, uses defaults)
        """
        if config:
            self.G = goal_value if goal_value is not None else config.actr_goal_value
            self.noise_stddev = (
                noise_stddev if noise_stddev is not None else config.actr_noise_stddev
            )
            model_to_use = model if model is not None else config.llm_model
            self.llm = LLMClient(model=model_to_use, config=config)
        else:
            # Backward compatibility: use defaults if no config
            self.G = goal_value if goal_value is not None else 10.0
            self.noise_stddev = noise_stddev if noise_stddev is not None else 0.5
            model_to_use = model if model is not None else "qwen3:8b"
            self.llm = LLMClient(model=model_to_use)
        self.context_manager = ContextWindowManager()

    async def resolve(
        self,
        operators: List[Operator],
        state: EditorState,
        goal: Goal,
        verbose: bool = True,
    ) -> Optional[Tuple[Operator, float]]:
        """
        Use LLM to estimate utilities and select best operator.

        Args:
            operators: List of operators to choose from
            state: Current state
            goal: Current goal
            verbose: Print reasoning

        Returns:
            (selected_operator, utility) or None if LLM fails
        """
        if not operators:
            return None

        # Compress state for LLM context
        state_summary = self.context_manager.compress_state(state, goal)

        # Create prompt
        operator_names = [op.name for op in operators]
        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary=state_summary,
            goal=goal.description,
            operators=operator_names,
            goal_value=self.G,
        )

        # Query LLM
        if verbose:
            print(f"   🤖 Querying LLM for utility estimates...")

        try:
            evaluation: Optional[UtilityEvaluation] = await self.llm.structured_query(
                prompt=prompt,
                response_schema=UtilityEvaluation,
                system_prompt=PromptTemplates.SYSTEM_PROMPT,
                temperature=0.3,
            )

            if not evaluation:
                if verbose:
                    print(f"   ✗ LLM query failed")
                return None

            # Calculate utilities
            utilities = []
            for op, est in zip(operators, evaluation.evaluations):
                P = est.probability_of_success
                C = est.estimated_cost
                noise = random.gauss(0, self.noise_stddev)

                U = P * self.G - C + noise

                utilities.append((op, U, est))

                if verbose:
                    print(
                        f"   {op.name}: U={U:.2f} "
                        f"(P={P:.2f}, C={C:.1f}, noise={noise:+.2f})"
                    )
                    print(f"      └─ {est.reasoning}")

            # Select highest utility
            best_op, best_U, best_est = max(utilities, key=lambda x: x[1])

            if verbose:
                print(f"   ✓ Selected: {best_op.name} (U={best_U:.2f})")
                print(f"   Recommendation: {evaluation.recommendation}")

            return (best_op, best_U)

        except Exception as e:
            if verbose:
                print(f"   ✗ Error during LLM query: {e}")
            return None

    async def generate_operators(
        self,
        state: EditorState,
        goal: Goal,
        verbose: bool = True,
    ) -> Optional[List[Operator]]:
        """
        Generate operators from scratch when no rules match (NO_CHANGE impasse).

        Uses LLM to suggest operators based on current state and goal.

        Args:
            state: Current state
            goal: Current goal
            verbose: Print reasoning

        Returns:
            List of suggested operators or None if LLM fails
        """
        try:
            # Compress state for LLM
            state_summary = self.context_manager.compress_state(state, goal)

            # Get recent error if available
            error = state.error_log[-1] if state.error_log else None

            # Create prompt
            prompt = PromptTemplates.generate_operators_prompt(
                state_summary=state_summary,
                goal=goal.description,
                error=error,
            )

            if verbose:
                print(f"   🤖 Querying LLM for operator suggestions...")

            # Query LLM for operator suggestions
            response = await self.llm.structured_query(
                prompt=prompt,
                response_schema=OperatorProposal,
                system_prompt=PromptTemplates.SYSTEM_PROMPT,
            )

            if not response:
                return None

            # Convert suggestions to actual operators
            operators = []
            for suggestion in response.operators:
                op = self._create_operator_from_suggestion(suggestion)
                if op:
                    operators.append(op)
                    if verbose:
                        print(f"   💡 Suggested: {op.name} - {suggestion.reasoning}")

            return operators if operators else None

        except Exception as e:
            if verbose:
                print(f"   ✗ Error generating operators: {e}")
            return None

    def _create_operator_from_suggestion(
        self, suggestion: OperatorSuggestion
    ) -> Optional[Operator]:
        """
        Convert an LLM operator suggestion into an actual Operator object.

        Args:
            suggestion: Operator suggestion from LLM

        Returns:
            Operator instance or None if suggestion is invalid
        """
        op_name = suggestion.name.lower()
        params = suggestion.parameters

        # Map LLM suggestions to actual operators
        if op_name == "read_file" and "path" in params:
            return OpReadFile(params["path"])
        elif op_name == "list_dir":
            path = params.get("path", ".")
            return OpListDirectory(path)
        # Add more operator types as needed
        else:
            # Unknown operator type - skip it
            return None

    def estimate_single_utility(
        self, operator: Operator, P: float, C: float
    ) -> float:
        """
        Calculate utility for a single operator with given P and C.

        Useful for testing or when P/C are known without LLM.

        Args:
            operator: Operator to evaluate
            P: Probability of success (0.0-1.0)
            C: Cost (1.0-10.0)

        Returns:
            Utility value
        """
        noise = random.gauss(0, self.noise_stddev)
        return P * self.G - C + noise

    def __repr__(self) -> str:
        return (
            f"ACTRResolver(G={self.G}, noise_stddev={self.noise_stddev}, "
            f"model={self.llm.model})"
        )


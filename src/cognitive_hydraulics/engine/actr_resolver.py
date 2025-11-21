"""ACT-R style conflict resolution using LLM for utility estimation."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import UtilityEvaluation, UtilityEstimate
from cognitive_hydraulics.llm.prompts import PromptTemplates
from cognitive_hydraulics.utils.context_manager import ContextWindowManager


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
        goal_value: float = 10.0,
        noise_stddev: float = 0.5,
        model: str = "qwen2.5:8b",
    ):
        """
        Initialize ACT-R resolver.

        Args:
            goal_value: Value G in utility equation (higher = more important)
            noise_stddev: Standard deviation for noise term
            model: LLM model to use
        """
        self.G = goal_value
        self.noise_stddev = noise_stddev
        self.llm = LLMClient(model=model)
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


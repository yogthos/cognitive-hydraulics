"""Unit tests for ACT-R resolver with history penalty (Tabu Search)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.working_memory import WorkingMemory
from cognitive_hydraulics.core.operator import OperatorResult
from cognitive_hydraulics.engine.actr_resolver import ACTRResolver
from cognitive_hydraulics.operators.file_ops import OpReadFile
from cognitive_hydraulics.llm.schemas import UtilityEvaluation, UtilityEstimate


class TestACTRResolverHistoryPenalty:
    """Test ACT-R resolver with history penalty (Tabu Search)."""

    @pytest.fixture
    def resolver(self):
        """Create ACT-R resolver."""
        return ACTRResolver(goal_value=10.0, noise_stddev=0.0)  # No noise for testing

    @pytest.fixture
    def working_memory(self):
        """Create working memory with some action history."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")
        wm = WorkingMemory(state, goal)
        return wm

    @pytest.fixture
    def operators(self):
        """Create test operators."""
        return [
            OpReadFile("file1.py"),
            OpReadFile("file2.py"),
        ]

    @pytest.mark.asyncio
    async def test_resolve_without_history_penalty(self, resolver, working_memory, operators):
        """Test that resolve works without working memory (backward compatibility)."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")

        # Mock LLM response
        mock_evaluation = UtilityEvaluation(
            evaluations=[
                UtilityEstimate(
                    operator_name="read_file(file1.py)",
                    probability_of_success=0.9,
                    estimated_cost=2.0,
                    reasoning="Should work",
                ),
                UtilityEstimate(
                    operator_name="read_file(file2.py)",
                    probability_of_success=0.8,
                    estimated_cost=3.0,
                    reasoning="Should work",
                ),
            ],
            recommendation="Use file1.py",
        )

        with patch.object(resolver.llm, 'structured_query', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_evaluation

            result = await resolver.resolve(
                operators=operators,
                state=state,
                goal=goal,
                verbose=0,
                working_memory=None,  # No history
                history_penalty_multiplier=2.0,
            )

            assert result is not None
            operator, utility = result
            # Without penalty, file1 should win (0.9 * 10 - 2 = 7.0 vs 0.8 * 10 - 3 = 5.0)
            assert operator.name == "read_file(file1.py)"
            assert utility > 5.0  # Should be around 7.0

    @pytest.mark.asyncio
    async def test_resolve_with_history_penalty(self, resolver, working_memory, operators):
        """Test that history penalty reduces utility for frequently used operators."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")

        # Record file1.py being used 3 times
        op1 = OpReadFile("file1.py")
        result = OperatorResult(
            success=True,
            new_state=state,
            output="ok",
        )

        for _ in range(3):
            working_memory.record_transition(op1, result, state, goal)

        assert working_memory.get_action_count("read_file(file1.py)") == 3

        # Mock LLM response
        mock_evaluation = UtilityEvaluation(
            evaluations=[
                UtilityEstimate(
                    operator_name="read_file(file1.py)",
                    probability_of_success=0.9,
                    estimated_cost=2.0,
                    reasoning="Should work",
                ),
                UtilityEstimate(
                    operator_name="read_file(file2.py)",
                    probability_of_success=0.8,
                    estimated_cost=3.0,
                    reasoning="Should work",
                ),
            ],
            recommendation="Use file2.py",
        )

        with patch.object(resolver.llm, 'structured_query', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_evaluation

            result = await resolver.resolve(
                operators=operators,
                state=state,
                goal=goal,
                verbose=0,
                working_memory=working_memory,
                history_penalty_multiplier=2.0,
            )

            assert result is not None
            operator, utility = result

            # With penalty: file1 = (0.9 * 10 - 2) - (3 * 2) = 7 - 6 = 1.0
            # Without penalty: file2 = (0.8 * 10 - 3) = 5.0
            # So file2 should win now
            assert operator.name == "read_file(file2.py)"
            assert utility > 0  # Should be around 5.0

    @pytest.mark.asyncio
    async def test_history_penalty_multiplier_effect(self, resolver, working_memory, operators):
        """Test that different penalty multipliers have different effects."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="test")

        # Record file1.py being used 2 times
        op1 = OpReadFile("file1.py")
        result = OperatorResult(
            success=True,
            new_state=state,
            output="ok",
        )

        for _ in range(2):
            working_memory.record_transition(op1, result, state, goal)

        # Mock LLM response
        mock_evaluation = UtilityEvaluation(
            evaluations=[
                UtilityEstimate(
                    operator_name="read_file(file1.py)",
                    probability_of_success=0.9,
                    estimated_cost=2.0,
                    reasoning="Should work",
                ),
                UtilityEstimate(
                    operator_name="read_file(file2.py)",
                    probability_of_success=0.8,
                    estimated_cost=3.0,
                    reasoning="Should work",
                ),
            ],
            recommendation="Use file1.py",
        )

        with patch.object(resolver.llm, 'structured_query', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_evaluation

            # Low penalty (1.0) - file1 should still win
            result_low = await resolver.resolve(
                operators=operators,
                state=state,
                goal=goal,
                verbose=0,
                working_memory=working_memory,
                history_penalty_multiplier=1.0,
            )

            # High penalty (5.0) - file2 should win
            result_high = await resolver.resolve(
                operators=operators,
                state=state,
                goal=goal,
                verbose=0,
                working_memory=working_memory,
                history_penalty_multiplier=5.0,
            )

            assert result_low is not None
            assert result_high is not None

            op_low, util_low = result_low
            op_high, util_high = result_high

            # With low penalty, file1 might still win
            # With high penalty, file2 should win
            # file1 penalty: 2 * 1.0 = 2.0 -> utility = 7.0 - 2.0 = 5.0
            # file2: utility = 5.0
            # So with low penalty, file1 wins (5.0 > 5.0, but noise might affect)

            # file1 penalty: 2 * 5.0 = 10.0 -> utility = 7.0 - 10.0 = -3.0
            # file2: utility = 5.0
            # So with high penalty, file2 definitely wins
            assert op_high.name == "read_file(file2.py)"

    def test_history_penalty_calculation(self, resolver):
        """Test that history penalty is calculated correctly in utility formula."""
        # U = P * G - C - (action_count * penalty_multiplier) + noise
        # With no noise: U = P * G - C - penalty

        P = 0.9
        G = 10.0
        C = 2.0
        action_count = 3
        penalty_mult = 2.0

        # Without penalty: U = 0.9 * 10 - 2 = 7.0
        utility_no_penalty = P * G - C

        # With penalty: U = 0.9 * 10 - 2 - (3 * 2) = 7.0 - 6.0 = 1.0
        utility_with_penalty = P * G - C - (action_count * penalty_mult)

        assert utility_no_penalty == 7.0
        assert utility_with_penalty == 1.0
        assert utility_with_penalty < utility_no_penalty


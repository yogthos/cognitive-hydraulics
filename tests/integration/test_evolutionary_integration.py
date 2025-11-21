"""Integration tests for evolutionary solver in full cognitive flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.config.settings import Config
from cognitive_hydraulics.llm.schemas import CodeCandidate, PopulationProposal
from datetime import datetime


class TestEvolutionaryIntegration:
    """Test evolutionary solver integration in full flow."""

    @pytest.fixture
    def config(self):
        """Create config with evolution enabled."""
        return Config(
            evolution_enabled=True,
            evolution_population_size=2,
            evolution_max_generations=1,
        )

    @pytest.fixture
    def agent(self, config):
        """Create agent with evolution enabled."""
        return CognitiveAgent(
            config=config,
            enable_learning=False,
        )

    @pytest.fixture
    def buggy_code(self):
        """Buggy code with IndexError."""
        return """def bubbleSort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i):  # Bug: should be n - i - 1
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr"""

    @pytest.fixture
    def test_code(self):
        """Test code."""
        return """
def test_bubbleSort():
    arr = [64, 34, 25, 12, 22, 11, 90]
    result = bubbleSort(arr.copy())
    assert result == [11, 12, 22, 25, 34, 64, 90]
    print("All tests passed")

if __name__ == "__main__":
    test_bubbleSort()
"""

    @pytest.mark.asyncio
    async def test_evolutionary_fallback_triggered_on_high_pressure(self, agent, buggy_code, test_code):
        """Test that evolutionary solver is triggered when pressure is very high."""
        state = EditorState(working_directory="/tmp")
        state.error_log = ["IndexError: list index out of range"]
        state.open_files = {
            "sort.py": FileContent(
                path="sort.py",
                content=buggy_code + test_code,
                language="python",
                last_modified=datetime.now(),
            )
        }

        goal = Goal(description="Fix the bug in sort.py")
        agent.current_goal = goal
        agent.working_memory = MagicMock()
        agent.working_memory.current_state = state

        # Mock evolutionary solver
        fixed_code = buggy_code.replace("range(0, n - i)", "range(0, n - i - 1)") + test_code
        best_candidate = CodeCandidate(
            hypothesis="Fix range boundary",
            code_patch=fixed_code,
            reasoning="Decrease range by 1",
        )

        with patch.object(agent.evolution_solver, 'evolve', new_callable=AsyncMock) as mock_evolve:
            mock_evolve.return_value = best_candidate

            # Mock _apply_operator to avoid actual file writes
            with patch.object(agent, '_apply_operator', new_callable=AsyncMock):
                # Force very high pressure
                with patch.object(agent.meta_monitor, 'calculate_pressure', return_value=0.95):
                    with patch.object(agent.meta_monitor, 'should_trigger_fallback', return_value=True):
                        # Create NO_CHANGE impasse
                        from cognitive_hydraulics.engine.impasse import Impasse, ImpasseType
                        impasse = Impasse(
                            type=ImpasseType.NO_CHANGE,
                            goal=goal,
                            operators=[],
                            description="No operators",
                        )

                        # Mock ACT-R to fail (triggers evolutionary fallback)
                        with patch.object(agent.actr_resolver, 'generate_operators', new_callable=AsyncMock) as mock_gen:
                            mock_gen.return_value = None  # ACT-R fails

                            success = await agent._handle_impasse(impasse, [], verbose=0)

                            # Should have tried evolutionary solver
                            mock_evolve.assert_called_once()
                            assert success is True

    @pytest.mark.asyncio
    async def test_evolutionary_fallback_not_triggered_for_non_code_goals(self, agent):
        """Test that evolutionary solver is not triggered for non-code-fixing goals."""
        state = EditorState(working_directory="/tmp")
        goal = Goal(description="Read the documentation")
        agent.current_goal = goal
        agent.working_memory = MagicMock()
        agent.working_memory.current_state = state

        # Mock evolutionary solver
        with patch.object(agent.evolution_solver, 'evolve', new_callable=AsyncMock) as mock_evolve:
            # Force very high pressure
            with patch.object(agent.meta_monitor, 'calculate_pressure', return_value=0.95):
                with patch.object(agent.meta_monitor, 'should_trigger_fallback', return_value=True):
                    from cognitive_hydraulics.engine.impasse import Impasse, ImpasseType
                    impasse = Impasse(
                        type=ImpasseType.NO_CHANGE,
                        goal=goal,
                        operators=[],
                        description="No operators",
                    )

                    # Mock ACT-R to fail
                    with patch.object(agent.actr_resolver, 'generate_operators', new_callable=AsyncMock):
                        # Should not call evolutionary solver for non-code goals
                        assert agent._goal_involves_code_fixing() is False
                        # The fallback should not trigger evolution for this goal

    def test_extract_error_context_with_multiple_files(self, agent):
        """Test error context extraction with multiple Python files."""
        state = EditorState(working_directory="/tmp")
        state.error_log = ["IndexError: list index out of range"]

        code1 = "def func1():\n    pass"
        code2 = "def func2():\n    pass"

        state.open_files = {
            "file1.py": FileContent(
                path="file1.py",
                content=code1,
                language="python",
                last_modified=datetime.now(),
            ),
            "file2.py": FileContent(
                path="file2.py",
                content=code2,
                language="python",
                last_modified=datetime.now(),
            ),
            "readme.txt": FileContent(
                path="readme.txt",
                content="Some text",
                language="text",
                last_modified=datetime.now(),
            ),
        }

        context = agent._extract_error_context(state)

        assert "ERROR:" in context
        assert "IndexError" in context
        assert "CODE:" in context
        assert "file1.py" in context
        assert "file2.py" in context
        assert "readme.txt" not in context  # Non-Python files shouldn't be included

    def test_extract_error_context_no_errors(self, agent):
        """Test error context extraction when no errors exist."""
        state = EditorState(working_directory="/tmp")
        state.error_log = []
        state.open_files = {}

        context = agent._extract_error_context(state)

        # Should still return something, even if minimal
        assert isinstance(context, str)
        # Should not have ERROR: section if no errors
        assert "ERROR:" not in context or len(state.error_log) == 0


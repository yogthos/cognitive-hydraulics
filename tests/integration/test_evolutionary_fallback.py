"""Integration tests for evolutionary fallback in CognitiveAgent."""

import pytest
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.config.settings import Config


class TestEvolutionaryFallback:
    """Test evolutionary solver integration with CognitiveAgent."""

    @pytest.fixture
    def config(self):
        """Create a test config with evolution enabled."""
        return Config(
            evolution_enabled=True,
            evolution_population_size=2,  # Small for testing
            evolution_max_generations=1,  # Small for testing
        )

    @pytest.fixture
    def agent(self, config):
        """Create a CognitiveAgent with evolution enabled."""
        return CognitiveAgent(
            config=config,
            enable_learning=False,  # Disable learning for faster tests
        )

    def test_goal_involves_code_fixing(self, agent):
        """Test detection of code fixing goals."""
        state = EditorState(working_directory="/tmp")
        goal1 = Goal(description="Fix the bug in sort.py")
        goal2 = Goal(description="Read the file")
        goal3 = Goal(description="Sort the list correctly")

        agent.current_goal = goal1
        assert agent._goal_involves_code_fixing() is True

        agent.current_goal = goal2
        assert agent._goal_involves_code_fixing() is False

        agent.current_goal = goal3
        assert agent._goal_involves_code_fixing() is True

    def test_extract_error_context(self, agent):
        """Test error context extraction."""
        state = EditorState(working_directory="/tmp")
        state.error_log = ["IndexError: list index out of range"]

        from datetime import datetime
        code = "def bubbleSort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]"
        state.open_files = {
            "sort.py": FileContent(
                path="sort.py",
                content=code,
                language="python",
                last_modified=datetime.now(),
            )
        }
        state.last_output = "STDOUT:\nIndexError at line 6"

        agent.working_memory = type('obj', (object,), {'current_state': state})()

        context = agent._extract_error_context(state)

        assert "ERROR:" in context
        assert "IndexError" in context
        assert "CODE:" in context
        assert "sort.py" in context
        assert "bubbleSort" in context
        assert "LAST OUTPUT:" in context

    def test_history_penalty_in_config(self, config):
        """Test that history penalty multiplier is in config."""
        assert hasattr(config, 'cognitive_history_penalty_multiplier')
        assert config.cognitive_history_penalty_multiplier == 2.0

    def test_evolution_config_defaults(self):
        """Test that evolution config has correct defaults."""
        default_config = Config()  # Use default config
        assert default_config.evolution_enabled is True
        assert default_config.evolution_population_size == 3  # Default from plan
        assert default_config.evolution_max_generations == 3

    def test_evolution_solver_initialized(self, agent):
        """Test that evolutionary solver is initialized when enabled."""
        # Evolution should be enabled if config says so
        assert hasattr(agent, 'evolution_enabled')
        # Solver may be None if LLM unavailable, but attribute should exist
        assert hasattr(agent, 'evolution_solver')


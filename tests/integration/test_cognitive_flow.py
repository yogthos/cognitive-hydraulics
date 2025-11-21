"""Integration tests for cognitive agent decision flow."""

import pytest
from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent


class TestCognitiveFlow:
    """Integration tests for the full cognitive decision flow."""

    def test_agent_creation(self):
        """Test creating cognitive agent."""
        agent = CognitiveAgent()

        assert agent.rule_engine is not None
        assert agent.meta_monitor is not None
        assert agent.impasse_detector is not None
        assert agent.actr_resolver is not None
        # Working memory is initialized in solve()
        assert agent.working_memory is None

    def test_agent_initial_state(self):
        """Test agent starts with empty state."""
        agent = CognitiveAgent()

        assert agent.current_goal is None
        assert len(agent.goal_stack) == 0
        # Working memory is None until solve()
        assert agent.working_memory is None

    def test_create_initial_goal(self):
        """Test creating an initial goal for the agent."""
        agent = CognitiveAgent()

        goal = Goal(
            description="Read main.py and understand its structure",
            target_state={"understanding": "complete"},
        )

        agent.current_goal = goal

        assert agent.current_goal.description == "Read main.py and understand its structure"
        assert agent.current_goal.parent_goal is None

    def test_agent_has_actr_resolver(self):
        """Test that agent has ACT-R resolver configured."""
        agent = CognitiveAgent()

        assert agent.actr_resolver is not None
        assert agent.actr_resolver.G == 10.0  # Default goal value
        assert agent.actr_resolver.llm is not None

    def test_agent_max_cycles_configuration(self):
        """Test that agent has max cycles configured."""
        agent = CognitiveAgent(max_cycles=50)

        # Should be configurable
        assert agent.max_cycles == 50

        # Default
        agent_default = CognitiveAgent()
        assert agent_default.max_cycles == 100

    def test_agent_goal_stack(self):
        """Test that agent has goal stack for sub-goaling."""
        agent = CognitiveAgent()

        # Goal stack should start empty
        assert len(agent.goal_stack) == 0
        assert isinstance(agent.goal_stack, list)

        # Should be able to push goals
        goal = Goal(description="Test")
        agent.goal_stack.append(goal)
        assert len(agent.goal_stack) == 1

    def test_agent_repr(self):
        """Test agent string representation."""
        agent = CognitiveAgent()

        repr_str = repr(agent)

        assert "CognitiveAgent" in repr_str

    @pytest.mark.asyncio
    async def test_agent_decision_cycle_structure(self):
        """Test that agent has proper decision cycle structure."""
        agent = CognitiveAgent()

        # Agent should have solve method for async execution
        assert hasattr(agent, "solve")
        assert callable(agent.solve)

        # Agent should have decision cycle components
        assert agent.rule_engine is not None
        assert agent.impasse_detector is not None


class TestSystemIntegration:
    """Test integration between different system components."""

    def test_all_components_available(self):
        """Test that all system components can be imported and created."""
        from cognitive_hydraulics.core import EditorState, Goal, WorkingMemory, Operator
        from cognitive_hydraulics.engine import (
            RuleEngine,
            MetaCognitiveMonitor,
            ImpasseDetector,
            CognitiveAgent,
            ACTRResolver,
        )
        from cognitive_hydraulics.llm import (
            LLMClient,
            OperatorProposal,
            UtilityEvaluation,
        )
        from cognitive_hydraulics.operators import OpReadFile, OpListDirectory
        from cognitive_hydraulics.utils import CodeAnalyzer, ContextWindowManager

        # All imports should succeed
        assert EditorState is not None
        assert Goal is not None
        assert WorkingMemory is not None
        assert Operator is not None
        assert RuleEngine is not None
        assert MetaCognitiveMonitor is not None
        assert ImpasseDetector is not None
        assert CognitiveAgent is not None
        assert ACTRResolver is not None
        assert LLMClient is not None
        assert OperatorProposal is not None
        assert UtilityEvaluation is not None
        assert OpReadFile is not None
        assert OpListDirectory is not None
        assert CodeAnalyzer is not None
        assert ContextWindowManager is not None

    def test_agent_components_work_together(self):
        """Test that agent components are properly connected."""
        agent = CognitiveAgent()

        # Core components should be initialized
        components = [
            agent.rule_engine,
            agent.meta_monitor,
            agent.impasse_detector,
            agent.actr_resolver,
        ]

        for component in components:
            assert component is not None

        # Working memory is initialized in solve()
        assert agent.working_memory is None

        # ACT-R resolver should have LLM client
        assert agent.actr_resolver.llm is not None

        # Meta monitor should have thresholds
        assert agent.meta_monitor.depth_threshold > 0
        assert agent.meta_monitor.time_threshold_ms > 0

    def test_phase_completion_markers(self):
        """Test that all implemented phases are accessible."""
        # Phase 0: Bootstrap ✓
        from cognitive_hydraulics import __version__

        # Phase 1: Core Models ✓
        from cognitive_hydraulics.core import EditorState, Goal, WorkingMemory

        # Phase 2: Tree-sitter Integration ✓
        from cognitive_hydraulics.utils import CodeAnalyzer, ContextWindowManager

        # Phase 3: Soar Decision Engine ✓
        from cognitive_hydraulics.engine import (
            RuleEngine,
            MetaCognitiveMonitor,
            ImpasseDetector,
        )

        # Phase 4: LLM Integration ✓
        from cognitive_hydraulics.llm import LLMClient, UtilityEvaluation
        from cognitive_hydraulics.engine import ACTRResolver

        # All phases complete up to Phase 4
        assert __version__ is not None


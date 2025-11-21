"""Integration tests for NO_CHANGE impasse handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent
from cognitive_hydraulics.engine.impasse import Impasse, ImpasseType
from cognitive_hydraulics.safety import SafetyConfig
from cognitive_hydraulics.operators.file_ops import OpReadFile


class TestNOChangeImpasseHandling:
    """Tests for NO_CHANGE impasse handling with low pressure."""

    @pytest.mark.asyncio
    async def test_no_change_impasse_low_pressure_calls_actr(self):
        """Test that NO_CHANGE impasse with low pressure calls ACT-R to generate operators."""
        agent = CognitiveAgent(
            safety_config=SafetyConfig(dry_run=True),
            enable_learning=False,
            max_cycles=10,
        )

        # Create a state that will trigger NO_CHANGE impasse
        # (file already open, no rules match)
        from cognitive_hydraulics.core.state import FileContent
        from datetime import datetime
        state = EditorState(
            working_directory="/test",
            open_files={
                "test.py": FileContent(
                    path="test.py",
                    content="test",
                    language="python",
                    last_modified=datetime.now(),
                )
            },
        )
        goal = Goal(description="Analyze test.py for bugs")
        agent.current_goal = goal
        agent.working_memory = MagicMock()
        agent.working_memory.current_state = state

        # Create NO_CHANGE impasse
        impasse = Impasse(
            type=ImpasseType.NO_CHANGE,
            goal=goal,
            operators=[],
            description="No operators proposed",
        )

        # Mock the ACT-R resolver to track if it's called
        with patch.object(agent.actr_resolver, 'generate_operators') as mock_generate:
            # Mock successful operator generation
            mock_op = OpReadFile("test.py")
            mock_generate.return_value = [mock_op]

            # Mock the resolve method to return a result
            with patch.object(agent.actr_resolver, 'resolve') as mock_resolve:
                mock_resolve.return_value = (mock_op, 5.0)

                # Mock _apply_operator to avoid actual execution
                with patch.object(agent, '_apply_operator', new_callable=AsyncMock):
                    # Handle impasse (should call ACT-R for low pressure)
                    success = await agent._handle_impasse(impasse, [], verbose=0)

                    # Verify ACT-R was called to generate operators
                    mock_generate.assert_called_once()
                    # Should have been called with current state and goal
                    call_args = mock_generate.call_args
                    assert call_args[0][0] == state  # First arg is state
                    assert call_args[0][1] == goal  # Second arg is goal

    @pytest.mark.asyncio
    async def test_no_change_impasse_high_pressure_calls_actr(self):
        """Test that NO_CHANGE impasse with high pressure also calls ACT-R."""
        agent = CognitiveAgent(
            safety_config=SafetyConfig(dry_run=True),
            enable_learning=False,
            max_cycles=10,
            depth_threshold=1,  # Low threshold to trigger high pressure quickly
        )

        state = EditorState(working_directory="/test")
        goal = Goal(description="Test goal")
        agent.current_goal = goal
        agent.working_memory = MagicMock()
        agent.working_memory.current_state = state

        # Create NO_CHANGE impasse
        impasse = Impasse(
            type=ImpasseType.NO_CHANGE,
            goal=goal,
            operators=[],
            description="No operators proposed",
        )

        # Mock ACT-R resolver
        with patch.object(agent.actr_resolver, 'generate_operators') as mock_generate:
            mock_op = OpReadFile("test.py")
            mock_generate.return_value = [mock_op]

            with patch.object(agent.actr_resolver, 'resolve') as mock_resolve:
                mock_resolve.return_value = (mock_op, 5.0)

                # Mock _apply_operator
                with patch.object(agent, '_apply_operator', new_callable=AsyncMock):
                    # Force high pressure by setting metrics
                    with patch.object(agent.meta_monitor, 'should_trigger_fallback', return_value=True):
                        success = await agent._handle_impasse(impasse, [], verbose=0)

                        # Should still call ACT-R even with high pressure
                        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_change_impasse_thinking_output(self):
        """Test that NO_CHANGE impasse generates thinking output."""
        agent = CognitiveAgent(
            safety_config=SafetyConfig(dry_run=True),
            enable_learning=False,
        )

        state = EditorState(working_directory="/test")
        goal = Goal(description="Test")
        agent.current_goal = goal
        agent.working_memory = MagicMock()
        agent.working_memory.current_state = state

        impasse = Impasse(
            type=ImpasseType.NO_CHANGE,
            goal=goal,
            operators=[],
            description="No operators",
        )

        # Capture output
        import io
        import sys
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            with patch.object(agent.actr_resolver, 'generate_operators', return_value=None):
                await agent._handle_impasse(impasse, [], verbose=2)  # Thinking mode

        output = f.getvalue()

        # Should contain thinking output
        assert "THINKING:" in output or "Generating Operators with ACT-R" in output

    def test_rule_engine_propose_operators_with_reasoning(self):
        """Test that RuleEngine.propose_operators_with_reasoning returns reasoning."""
        from cognitive_hydraulics.engine.rule_engine import RuleEngine

        engine = RuleEngine()
        state = EditorState(working_directory=".")
        goal = Goal(description="list files")

        # Should return (operator, priority, reason) tuples
        proposals = engine.propose_operators_with_reasoning(state, goal)

        if proposals:
            op, priority, reason = proposals[0]
            assert isinstance(op, type) or hasattr(op, 'name')
            assert isinstance(priority, (int, float))
            assert isinstance(reason, str)
            assert len(reason) > 0  # Should have a reason


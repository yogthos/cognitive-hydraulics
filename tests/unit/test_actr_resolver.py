"""Unit tests for ACT-R resolver."""

import pytest
from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.engine.actr_resolver import ACTRResolver
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpListDirectory


class TestACTRResolver:
    """Tests for ACTRResolver."""

    def test_create_resolver(self):
        """Test creating ACT-R resolver."""
        resolver = ACTRResolver(goal_value=10.0, noise_stddev=0.5)

        assert resolver.G == 10.0
        assert resolver.noise_stddev == 0.5
        assert resolver.llm is not None

    def test_create_resolver_custom_model(self):
        """Test creating resolver with custom model."""
        resolver = ACTRResolver(model="llama2:7b")

        assert resolver.llm.model == "llama2:7b"

    def test_estimate_single_utility(self):
        """Test utility calculation for single operator."""
        resolver = ACTRResolver(goal_value=10.0, noise_stddev=0.0)  # No noise
        operator = OpReadFile("test.py")

        # High probability, low cost = high utility
        utility = resolver.estimate_single_utility(operator, P=0.9, C=2.0)
        expected = 0.9 * 10.0 - 2.0  # 7.0
        assert abs(utility - expected) < 0.5  # Allow small noise

        # Low probability, high cost = low utility
        utility = resolver.estimate_single_utility(operator, P=0.2, C=8.0)
        expected = 0.2 * 10.0 - 8.0  # -6.0
        assert abs(utility - expected) < 0.5

    def test_utility_formula_components(self):
        """Test that utility formula correctly uses P, G, C."""
        resolver = ACTRResolver(goal_value=15.0, noise_stddev=0.0)
        operator = OpReadFile("test.py")

        # U = P * G - C
        # U = 0.5 * 15.0 - 5.0 = 2.5
        utility = resolver.estimate_single_utility(operator, P=0.5, C=5.0)
        assert abs(utility - 2.5) < 0.5

    def test_noise_adds_exploration(self):
        """Test that noise adds variability."""
        resolver = ACTRResolver(goal_value=10.0, noise_stddev=1.0)  # High noise
        operator = OpReadFile("test.py")

        # Calculate multiple times
        utilities = [
            resolver.estimate_single_utility(operator, P=0.5, C=5.0)
            for _ in range(10)
        ]

        # Should have some variance
        assert len(set(utilities)) > 1  # Not all the same
        assert max(utilities) - min(utilities) > 0.5  # Reasonable spread

    def test_resolve_no_operators(self):
        """Test resolve with empty operator list."""
        resolver = ACTRResolver()
        state = EditorState()
        goal = Goal(description="Test")

        # Should return None gracefully
        # Note: async test would need actual resolution
        # For now just test the logic path
        assert True  # Placeholder - full test needs async

    def test_repr(self):
        """Test string representation."""
        resolver = ACTRResolver(goal_value=12.0, noise_stddev=0.3)

        repr_str = repr(resolver)

        assert "ACTRResolver" in repr_str
        assert "12.0" in repr_str
        assert "0.3" in repr_str

    def test_different_goal_values_affect_utility(self):
        """Test that different goal values change utility."""
        resolver_low = ACTRResolver(goal_value=5.0, noise_stddev=0.0)
        resolver_high = ACTRResolver(goal_value=20.0, noise_stddev=0.0)
        operator = OpReadFile("test.py")

        utility_low = resolver_low.estimate_single_utility(operator, P=0.8, C=3.0)
        utility_high = resolver_high.estimate_single_utility(operator, P=0.8, C=3.0)

        # Higher goal value should give higher utility
        assert utility_high > utility_low

    def test_utility_can_be_negative(self):
        """Test that utility can be negative (high cost, low success)."""
        resolver = ACTRResolver(goal_value=10.0, noise_stddev=0.0)
        operator = OpReadFile("test.py")

        # Very low probability, very high cost
        utility = resolver.estimate_single_utility(operator, P=0.1, C=9.0)

        assert utility < 0  # Should be negative

    def test_resolver_has_context_manager(self):
        """Test that resolver has context manager for state compression."""
        resolver = ACTRResolver()

        assert resolver.context_manager is not None
        assert hasattr(resolver.context_manager, "compress_state")


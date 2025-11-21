"""Unit tests for RuleEngine."""

import pytest
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.engine.rule_engine import Rule, RuleEngine
from cognitive_hydraulics.operators.file_ops import OpReadFile
from datetime import datetime


class TestRule:
    """Tests for Rule class."""

    def test_create_rule(self):
        """Test creating a simple rule."""
        rule = Rule(
            name="test_rule",
            condition=lambda s, g: True,
            operator_factory=lambda s, g: OpReadFile("test.py"),
            priority=2.0,
            description="Test rule",
        )

        assert rule.name == "test_rule"
        assert rule.priority == 2.0
        assert rule.description == "Test rule"

    def test_rule_matches_true(self):
        """Test rule matching when condition is true."""
        rule = Rule(
            name="always_matches",
            condition=lambda s, g: True,
            operator_factory=lambda s, g: OpReadFile("test.py"),
        )

        state = EditorState()
        goal = Goal(description="Test")

        assert rule.matches(state, goal)

    def test_rule_matches_false(self):
        """Test rule not matching when condition is false."""
        rule = Rule(
            name="never_matches",
            condition=lambda s, g: False,
            operator_factory=lambda s, g: OpReadFile("test.py"),
        )

        state = EditorState()
        goal = Goal(description="Test")

        assert not rule.matches(state, goal)

    def test_rule_create_operator(self):
        """Test creating operator from rule."""
        rule = Rule(
            name="test_rule",
            condition=lambda s, g: True,
            operator_factory=lambda s, g: OpReadFile("specific.py"),
        )

        state = EditorState()
        goal = Goal(description="Test")

        operator = rule.create_operator(state, goal)

        assert operator.name == "read_file(specific.py)"


class TestRuleEngine:
    """Tests for RuleEngine."""

    def test_create_engine(self):
        """Test creating rule engine with default rules."""
        engine = RuleEngine()

        assert len(engine.rules) >= 5  # Should have default rules
        assert all(isinstance(rule, Rule) for rule in engine.rules)

    def test_add_custom_rule(self):
        """Test adding a custom rule."""
        engine = RuleEngine()
        initial_count = len(engine.rules)

        custom_rule = Rule(
            name="custom_rule",
            condition=lambda s, g: "custom" in g.description,
            operator_factory=lambda s, g: OpReadFile("custom.py"),
            priority=10.0,
        )

        engine.add_rule(custom_rule)

        assert len(engine.rules) == initial_count + 1
        assert engine.rules[-1] == custom_rule

    def test_propose_operators_no_matches(self):
        """Test proposing operators when no rules match."""
        engine = RuleEngine()
        engine.rules = []  # Clear default rules

        state = EditorState()
        goal = Goal(description="Nothing matches")

        proposals = engine.propose_operators(state, goal)

        assert len(proposals) == 0

    def test_propose_operators_single_match(self):
        """Test proposing operators with one matching rule."""
        engine = RuleEngine()
        engine.rules = []  # Clear default rules

        engine.add_rule(
            Rule(
                name="only_match",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("match.py"),
                priority=5.0,
            )
        )

        state = EditorState()
        goal = Goal(description="Test")

        proposals = engine.propose_operators(state, goal)

        assert len(proposals) == 1
        operator, priority = proposals[0]
        assert operator.name == "read_file(match.py)"
        assert priority == 5.0

    def test_propose_operators_sorted_by_priority(self):
        """Test that proposals are sorted by priority (highest first)."""
        engine = RuleEngine()
        engine.rules = []

        # Add rules with different priorities
        engine.add_rule(
            Rule(
                name="low_priority",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("low.py"),
                priority=1.0,
            )
        )
        engine.add_rule(
            Rule(
                name="high_priority",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("high.py"),
                priority=10.0,
            )
        )
        engine.add_rule(
            Rule(
                name="medium_priority",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("medium.py"),
                priority=5.0,
            )
        )

        state = EditorState()
        goal = Goal(description="Test")

        proposals = engine.propose_operators(state, goal)

        assert len(proposals) == 3
        # Should be sorted: high(10), medium(5), low(1)
        assert proposals[0][1] == 10.0
        assert proposals[1][1] == 5.0
        assert proposals[2][1] == 1.0

    def test_get_best_operator(self):
        """Test getting the single best operator."""
        engine = RuleEngine()
        engine.rules = []

        engine.add_rule(
            Rule(
                name="best",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("best.py"),
                priority=10.0,
            )
        )
        engine.add_rule(
            Rule(
                name="worse",
                condition=lambda s, g: True,
                operator_factory=lambda s, g: OpReadFile("worse.py"),
                priority=1.0,
            )
        )

        state = EditorState()
        goal = Goal(description="Test")

        best = engine.get_best_operator(state, goal)

        assert best is not None
        operator, priority = best
        assert operator.name == "read_file(best.py)"
        assert priority == 10.0

    def test_default_rule_file_mentioned_in_goal(self):
        """Test default rule that opens files mentioned in goal."""
        engine = RuleEngine()

        state = EditorState()
        goal = Goal(description="Fix the bug in main.py")

        proposals = engine.propose_operators(state, goal)

        # Should propose opening main.py
        assert any("main.py" in op.name for op, _ in proposals)

    def test_default_rule_list_directory(self):
        """Test default rule that lists directory."""
        engine = RuleEngine()

        state = EditorState()  # No open files
        goal = Goal(description="List the files")

        proposals = engine.propose_operators(state, goal)

        # Should propose listing directory
        assert any("list_dir" in op.name for op, _ in proposals)

    def test_default_rule_error_mentions_file(self):
        """Test default rule that opens file from error."""
        engine = RuleEngine()

        state = EditorState()
        state.error_log.append("FileNotFoundError: broken.py")
        goal = Goal(description="Fix error")

        proposals = engine.propose_operators(state, goal)

        # Should propose opening broken.py
        assert any("broken.py" in op.name for op, _ in proposals)

    def test_rule_with_exception_doesnt_crash(self):
        """Test that rules with exceptions don't crash the engine."""
        engine = RuleEngine()
        engine.rules = []

        # Rule that raises exception
        def bad_condition(s, g):
            raise ValueError("Intentional error")

        engine.add_rule(
            Rule(
                name="bad_rule",
                condition=bad_condition,
                operator_factory=lambda s, g: OpReadFile("test.py"),
            )
        )

        state = EditorState()
        goal = Goal(description="Test")

        # Should not crash
        proposals = engine.propose_operators(state, goal)
        assert len(proposals) == 0  # Bad rule doesn't match


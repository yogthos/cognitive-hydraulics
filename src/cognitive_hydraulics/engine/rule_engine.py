"""Rule-based symbolic reasoning engine (Soar-inspired)."""

from __future__ import annotations

from typing import List, Callable, Optional
from dataclasses import dataclass

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpListDirectory


@dataclass
class Rule:
    """
    A symbolic production rule.

    Format: IF condition(state, goal) THEN propose operator
    """

    name: str
    condition: Callable[[EditorState, Goal], bool]
    operator_factory: Callable[[EditorState, Goal], Operator]
    priority: float = 1.0
    description: str = ""

    def matches(self, state: EditorState, goal: Goal) -> bool:
        """Check if this rule's condition is satisfied."""
        try:
            return self.condition(state, goal)
        except Exception:
            return False

    def create_operator(self, state: EditorState, goal: Goal) -> Operator:
        """Create the operator for this rule."""
        return self.operator_factory(state, goal)


class RuleEngine:
    """
    Symbolic pattern matcher for operator proposal.

    Implements the Soar-style production system where rules fire
    to propose operators based on current state and goal.
    """

    def __init__(self):
        self.rules: List[Rule] = []
        self._register_default_rules()

    def add_rule(self, rule: Rule) -> None:
        """Add a new rule to the engine."""
        self.rules.append(rule)

    def propose_operators(
        self, state: EditorState, goal: Goal
    ) -> List[tuple[Operator, float]]:
        """
        Match all rules against current state/goal.

        Returns:
            List of (operator, priority) tuples sorted by priority
        """
        proposals = []

        for rule in self.rules:
            if rule.matches(state, goal):
                try:
                    operator = rule.create_operator(state, goal)
                    proposals.append((operator, rule.priority))
                except Exception:
                    # Rule matched but couldn't create operator - skip
                    continue

        # Sort by priority (highest first)
        proposals.sort(key=lambda x: x[1], reverse=True)
        return proposals

    def get_best_operator(
        self, state: EditorState, goal: Goal
    ) -> Optional[tuple[Operator, float]]:
        """
        Get the single best operator (highest priority).

        Returns:
            (operator, priority) or None if no proposals
        """
        proposals = self.propose_operators(state, goal)
        return proposals[0] if proposals else None

    def _register_default_rules(self) -> None:
        """Register the default production rules."""

        # Rule 1: If file mentioned in goal but not open, read it
        self.add_rule(
            Rule(
                name="open_mentioned_file",
                description="Open a file mentioned in the goal",
                condition=lambda s, g: self._file_mentioned_but_not_open(s, g),
                operator_factory=lambda s, g: OpReadFile(
                    self._extract_filename_from_goal(g)
                ),
                priority=5.0,
            )
        )

        # Rule 2: If goal says "list" and no files open, list directory
        self.add_rule(
            Rule(
                name="list_directory_for_exploration",
                description="List directory when exploring",
                condition=lambda s, g: "list" in g.description.lower()
                and len(s.open_files) == 0,
                operator_factory=lambda s, g: OpListDirectory("."),
                priority=4.0,
            )
        )

        # Rule 3: If error mentions file not in open_files, read it
        self.add_rule(
            Rule(
                name="open_file_from_error",
                description="Open file mentioned in error",
                condition=lambda s, g: self._error_mentions_unopened_file(s),
                operator_factory=lambda s, g: OpReadFile(
                    self._extract_filename_from_error(s)
                ),
                priority=6.0,  # High priority - addressing errors
            )
        )

        # Rule 4: If no files open and goal is vague, explore directory
        self.add_rule(
            Rule(
                name="explore_when_lost",
                description="List directory when no context",
                condition=lambda s, g: len(s.open_files) == 0 and len(g.description) < 50,
                operator_factory=lambda s, g: OpListDirectory("."),
                priority=2.0,
            )
        )

        # Rule 5: If goal mentions "read", "check", "bug", or "fix", prioritize reading
        self.add_rule(
            Rule(
                name="read_for_inspection",
                description="Read files for inspection goals",
                condition=lambda s, g: any(
                    word in g.description.lower()
                    for word in ["read", "check", "inspect", "look", "bug", "fix", "analyze"]
                )
                and self._file_mentioned_but_not_open(s, g),
                operator_factory=lambda s, g: OpReadFile(
                    self._extract_filename_from_goal(g)
                ),
                priority=4.5,
            )
        )

    # Helper methods for rule conditions

    def _file_mentioned_but_not_open(self, state: EditorState, goal: Goal) -> bool:
        """Check if goal mentions a file that's not currently open."""
        import re

        # Look for file patterns in goal
        file_pattern = r"[\w\-\_]+\.\w+"
        matches = re.findall(file_pattern, goal.description)

        for filename in matches:
            if filename not in state.open_files:
                return True
        return False

    def _extract_filename_from_goal(self, goal: Goal) -> str:
        """Extract the first filename mentioned in goal."""
        import re

        file_pattern = r"[\w\-\_]+\.\w+"
        matches = re.findall(file_pattern, goal.description)
        return matches[0] if matches else "unknown.txt"

    def _error_mentions_unopened_file(self, state: EditorState) -> bool:
        """Check if recent error mentions a file not in open_files."""
        if not state.error_log:
            return False

        import re

        last_error = state.error_log[-1]
        file_pattern = r"[\w\-\_]+\.\w+"
        matches = re.findall(file_pattern, last_error)

        for filename in matches:
            if filename not in state.open_files:
                return True
        return False

    def _extract_filename_from_error(self, state: EditorState) -> str:
        """Extract the first filename from the most recent error."""
        import re

        last_error = state.error_log[-1]
        file_pattern = r"[\w\-\_]+\.\w+"
        matches = re.findall(file_pattern, last_error)
        return matches[0] if matches else "unknown.txt"

    def __repr__(self) -> str:
        return f"RuleEngine({len(self.rules)} rules)"


"""Rule-based symbolic reasoning engine (Soar-inspired)."""

from __future__ import annotations

from typing import List, Callable, Optional
from dataclasses import dataclass

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpListDirectory
from cognitive_hydraulics.operators.exec_ops import OpRunCode


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

    def propose_operators_with_reasoning(
        self, state: EditorState, goal: Goal
    ) -> List[tuple[Operator, float, str]]:
        """
        Match all rules against current state/goal with reasoning.

        Returns:
            List of (operator, priority, reason) tuples sorted by priority
        """
        proposals = []

        for rule in self.rules:
            if rule.matches(state, goal):
                try:
                    operator = rule.create_operator(state, goal)
                    reason = rule.description or f"Rule '{rule.name}' matched"
                    proposals.append((operator, rule.priority, reason))
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

        # Rule 6: If goal mentions "run", "execute", "test", or "fix bug" and file is open, run it
        # BUT: Don't run if there's already an error (let ACT-R generate fix operators instead)
        # AND: Don't run if goal is already achieved
        # AND: Don't run if we've already run it and tests exist but didn't pass (avoid infinite loop)
        self.add_rule(
            Rule(
                name="run_code_for_fix_goal",
                description="Execute code when goal mentions run/execute/test/fix",
                condition=lambda s, g: any(
                    word in g.description.lower()
                    for word in ["run", "execute", "test", "fix bug", "fix the bug"]
                )
                and self._file_mentioned_and_open(s, g)
                and self._is_python_file(self._extract_filename_from_goal(g))
                and len(s.error_log) == 0  # Only run if no errors yet
                and g.status != "success"  # Don't run if goal already achieved
                and not self._tests_exist_but_failed(s, g),  # Don't run if tests failed (avoid loop)
                operator_factory=lambda s, g: OpRunCode(
                    self._extract_filename_from_goal(g)
                ),
                priority=7.0,  # High priority - executing code
            )
        )

        # Rule 7: If file is open and goal mentions "fix" but no errors yet, run code to find errors
        # BUT: Don't run if goal is already achieved
        # AND: Don't run if we've already run it and tests exist but didn't pass (avoid infinite loop)
        self.add_rule(
            Rule(
                name="run_code_to_find_errors",
                description="Run code to discover errors when fixing bugs",
                condition=lambda s, g: "fix" in g.description.lower()
                and self._file_mentioned_and_open(s, g)
                and len(s.error_log) == 0
                and self._is_python_file(self._extract_filename_from_goal(g))
                and g.status != "success"  # Don't run if goal already achieved
                and not self._tests_exist_but_failed(s, g),  # Don't run if tests failed (avoid loop)
                operator_factory=lambda s, g: OpRunCode(
                    self._extract_filename_from_goal(g)
                ),
                priority=6.5,
            )
        )

        # Rule 8: If code runs successfully but tests exist and didn't pass, we need to fix the code
        # This creates an impasse that will trigger ACT-R to generate a fix
        # Actually, this is handled by the goal achievement check - if tests don't pass, goal isn't achieved
        # So we don't need a separate rule for this

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

    def _file_mentioned_and_open(self, state: EditorState, goal: Goal) -> bool:
        """Check if goal mentions a file that is currently open."""
        import re

        file_pattern = r"[\w\-\_]+\.\w+"
        matches = re.findall(file_pattern, goal.description)

        for filename in matches:
            if filename in state.open_files:
                return True
        return False

    def _is_python_file(self, filename: str) -> bool:
        """Check if filename is a Python file."""
        return filename.endswith(".py")

    def has_indexerror(self, state: EditorState) -> bool:
        """Check if error_log contains an IndexError."""
        if not state.error_log:
            return False
        return any("IndexError" in error for error in state.error_log)

    def _tests_exist_but_failed(self, state: EditorState, goal: Goal) -> bool:
        """Check if test functions exist but tests didn't pass (to avoid infinite loops)."""
        if not state.open_files:
            return False

        filename = self._extract_filename_from_goal(goal)
        if filename not in state.open_files:
            return False

        file_content = state.open_files[filename].content
        has_test = "def test_" in file_content

        if not has_test:
            return False

        # Check if we've run the code and it succeeded but tests didn't pass
        # This is indicated by: last_output exists, no errors in error_log, but no "All tests passed"
        if state.last_output:
            output_lower = state.last_output.lower()
            has_tests_passed = "all tests passed" in output_lower
            has_exit_code_0 = "exit code: 0" in output_lower or "exit code:0" in output_lower or "exit code: 0" in output_lower

            # If code ran successfully (exit code 0) but tests didn't pass, we've already tried
            # Also check if we've run it multiple times (check working memory history)
            if has_exit_code_0 and not has_tests_passed and len(state.error_log) == 0:
                # Count how many times we've run this code successfully
                # If it's more than once, we're in a loop
                return True  # Conservative: if tests exist but didn't pass, don't run again

        return False

    def __repr__(self) -> str:
        return f"RuleEngine({len(self.rules)} rules)"


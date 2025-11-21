"""Unit tests for LLM prompts."""

import pytest
from cognitive_hydraulics.llm.prompts import PromptTemplates


class TestPromptTemplates:
    """Tests for PromptTemplates."""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined."""
        assert len(PromptTemplates.SYSTEM_PROMPT) > 0
        assert "JSON" in PromptTemplates.SYSTEM_PROMPT
        assert "schema" in PromptTemplates.SYSTEM_PROMPT

    def test_generate_operators_prompt_basic(self):
        """Test generating operator proposal prompt."""
        state_summary = {
            "working_directory": "/project",
            "open_files": [],
        }
        goal = "Fix the bug"

        prompt = PromptTemplates.generate_operators_prompt(state_summary, goal)

        assert "Fix the bug" in prompt
        assert "/project" in prompt
        assert "operator" in prompt.lower()

    def test_generate_operators_prompt_with_error(self):
        """Test prompt generation with error context."""
        state_summary = {
            "working_directory": "/project",
            "open_files": ["main.py"],
        }
        goal = "Fix the error"
        error = "NameError: undefined variable"

        prompt = PromptTemplates.generate_operators_prompt(
            state_summary, goal, error
        )

        assert "NameError" in prompt
        assert "RECENT ERROR" in prompt

    def test_generate_operators_prompt_with_code(self):
        """Test prompt generation with code context."""
        state_summary = {
            "working_directory": "/project",
            "open_files": ["main.py"],
            "relevant_code": {
                "main.py": "def hello():\n    print('world')"
            },
        }
        goal = "Understand the code"

        prompt = PromptTemplates.generate_operators_prompt(state_summary, goal)

        assert "main.py" in prompt
        assert "RELEVANT CODE" in prompt
        assert "hello" in prompt

    def test_generate_operators_prompt_lists_available_ops(self):
        """Test that prompt lists available operator types."""
        state_summary = {"working_directory": ".", "open_files": []}
        goal = "Test"

        prompt = PromptTemplates.generate_operators_prompt(state_summary, goal)

        assert "read_file" in prompt
        assert "list_dir" in prompt
        assert "search" in prompt

    def test_evaluate_utilities_prompt_basic(self):
        """Test generating utility evaluation prompt."""
        state_summary = {
            "working_directory": "/project",
            "open_files": ["test.py"],
        }
        goal = "Fix bug"
        operators = ["read_file(main.py)", "list_dir(.)"]

        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary, goal, operators, goal_value=10.0
        )

        assert "Fix bug" in prompt
        assert "read_file(main.py)" in prompt
        assert "list_dir(.)" in prompt
        assert "10.0" in prompt  # Goal value

    def test_evaluate_utilities_prompt_explains_formula(self):
        """Test that prompt explains the utility formula."""
        state_summary = {"working_directory": ".", "open_files": []}
        goal = "Test"
        operators = ["op1"]

        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary, goal, operators
        )

        assert "U = P * G - C" in prompt
        assert "Probability" in prompt
        assert "Cost" in prompt

    def test_evaluate_utilities_prompt_with_error(self):
        """Test utility prompt with error context."""
        state_summary = {
            "working_directory": ".",
            "open_files": [],
            "error": "FileNotFoundError: missing.py",
        }
        goal = "Fix error"
        operators = ["read_file(missing.py)"]

        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary, goal, operators
        )

        assert "FileNotFoundError" in prompt

    def test_evaluate_utilities_prompt_cost_ranges(self):
        """Test that prompt explains cost ranges."""
        state_summary = {"working_directory": ".", "open_files": []}
        goal = "Test"
        operators = ["op1"]

        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary, goal, operators
        )

        assert "1-3" in prompt  # Quick operations
        assert "4-7" in prompt  # Medium operations
        assert "8-10" in prompt  # Expensive operations

    def test_compress_prompt_short_prompt(self):
        """Test that short prompts are not compressed."""
        short_prompt = "This is a short prompt"

        compressed = PromptTemplates.compress_prompt_if_needed(
            short_prompt, max_length=1000
        )

        assert compressed == short_prompt

    def test_compress_prompt_long_prompt(self):
        """Test that long prompts are compressed."""
        # Create a long prompt with code
        long_prompt = "Header\n```\n" + "x = 1\n" * 100 + "```\nFooter"

        compressed = PromptTemplates.compress_prompt_if_needed(
            long_prompt, max_length=200
        )

        assert len(compressed) < len(long_prompt)
        assert "truncated" in compressed
        assert "Header" in compressed
        assert "Footer" in compressed

    def test_compress_prompt_preserves_structure(self):
        """Test that compression preserves prompt structure."""
        prompt = "Important info\n```\nLong code...\n```\nMore info"

        compressed = PromptTemplates.compress_prompt_if_needed(
            prompt, max_length=50
        )

        # Should keep structure markers
        assert "Important info" in compressed
        assert "```" in compressed

    def test_prompts_are_actionable(self):
        """Test that prompts encourage actionable responses."""
        state = {"working_directory": ".", "open_files": []}

        op_prompt = PromptTemplates.generate_operators_prompt(state, "Test")
        util_prompt = PromptTemplates.evaluate_utilities_prompt(
            state, "Test", ["op1"]
        )

        assert "actionable" in op_prompt.lower() or "concrete" in op_prompt.lower()
        assert "estimate" in util_prompt.lower() or "recommend" in util_prompt.lower()


"""Unit tests for evolutionary solver prompts."""

import pytest
from cognitive_hydraulics.llm.prompts import PromptTemplates
from cognitive_hydraulics.llm.schemas import CodeCandidate


class TestEvolutionPrompts:
    """Test prompt generation for evolutionary solver."""

    def test_generate_population_prompt(self):
        """Test population generation prompt."""
        error_context = "IndexError: list index out of range at line 6"
        goal = "Fix the bug in sort.py"
        n = 3

        prompt = PromptTemplates.generate_population_prompt(
            error_context=error_context,
            goal=goal,
            n=n,
        )

        assert "GOAL:" in prompt
        assert goal in prompt
        assert "ERROR CONTEXT:" in prompt
        assert error_context in prompt
        assert f"Generate {n} DISTINCT hypotheses" in prompt
        assert "hypothesis" in prompt
        assert "code_patch" in prompt
        assert "reasoning" in prompt
        assert "DIVERSE APPROACHES" in prompt

    def test_generate_population_prompt_different_sizes(self):
        """Test population prompt with different sizes."""
        error_context = "Test error"
        goal = "Test goal"

        prompt_2 = PromptTemplates.generate_population_prompt(
            error_context=error_context,
            goal=goal,
            n=2,
        )

        prompt_5 = PromptTemplates.generate_population_prompt(
            error_context=error_context,
            goal=goal,
            n=5,
        )

        assert "Generate 2 DISTINCT hypotheses" in prompt_2
        assert "Generate 5 DISTINCT hypotheses" in prompt_5

    def test_mutate_candidate_prompt(self):
        """Test mutation prompt generation."""
        candidate = CodeCandidate(
            hypothesis="Fix range",
            code_patch="for j in range(0, n):\n    if arr[j] > arr[j+1]:\n        arr[j], arr[j+1] = arr[j+1], arr[j]",
            reasoning="Decrease range",
        )

        fitness_report = """- Syntax: PASS
- Runtime: PASS
- Correctness: FAIL
  Error: Tests did not pass"""

        prompt = PromptTemplates.mutate_candidate_prompt(
            candidate=candidate,
            fitness_report=fitness_report,
        )

        assert "Previous Attempt:" in prompt
        assert candidate.code_patch in prompt
        assert "Fitness Report:" in prompt
        assert fitness_report in prompt
        assert "Modify the code to fix the failures" in prompt
        assert "Do not change the function signature" in prompt

    def test_mutate_candidate_prompt_with_syntax_error(self):
        """Test mutation prompt with syntax error in fitness report."""
        candidate = CodeCandidate(
            hypothesis="Broken code",
            code_patch="def hello(\n    pass",  # Syntax error
            reasoning="Won't work",
        )

        fitness_report = """- Syntax: FAIL
  Error: SyntaxError: invalid syntax"""

        prompt = PromptTemplates.mutate_candidate_prompt(
            candidate=candidate,
            fitness_report=fitness_report,
        )

        assert candidate.code_patch in prompt
        assert "Syntax: FAIL" in prompt
        assert "SyntaxError" in prompt


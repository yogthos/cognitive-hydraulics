"""Unit tests for EvolutionarySolver."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from cognitive_hydraulics.engine.evolution import EvolutionarySolver
from cognitive_hydraulics.engine.evaluator import CodeEvaluator, EvaluationResult
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import CodeCandidate, PopulationProposal


class TestEvolutionarySolver:
    """Test EvolutionarySolver functionality."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client."""
        llm = MagicMock(spec=LLMClient)
        llm.structured_query = AsyncMock()
        return llm

    @pytest.fixture
    def evaluator(self):
        """Create a real CodeEvaluator."""
        return CodeEvaluator()

    @pytest.fixture
    def solver(self, mock_llm, evaluator):
        """Create an EvolutionarySolver with mocked dependencies."""
        return EvolutionarySolver(
            llm_client=mock_llm,
            evaluator=evaluator,
            config=None,
        )

    def test_format_fitness_report(self, solver):
        """Test fitness report formatting."""
        result = EvaluationResult(
            score=40,
            syntax_valid=True,
            runtime_valid=True,
            correctness_valid=False,
            error_message="Tests did not pass",
            output="Some output",
        )

        report = solver._format_fitness_report(result)
        assert "Syntax: PASS" in report
        assert "Runtime: PASS" in report
        assert "Correctness: FAIL" in report
        assert "Tests did not pass" in report

    def test_format_fitness_report_syntax_error(self, solver):
        """Test fitness report for syntax error."""
        result = EvaluationResult(
            score=0,
            syntax_valid=False,
            runtime_valid=False,
            correctness_valid=False,
            error_message="SyntaxError: invalid syntax",
        )

        report = solver._format_fitness_report(result)
        assert "Syntax: FAIL" in report
        assert "SyntaxError" in report

    @pytest.mark.asyncio
    async def test_generate_population(self, solver, mock_llm):
        """Test population generation."""
        # Mock LLM response
        candidates = [
            CodeCandidate(
                hypothesis="Fix range",
                code_patch="for j in range(0, n - 1):",
                reasoning="Decrease range",
            ),
            CodeCandidate(
                hypothesis="Add check",
                code_patch="if j+1 < n:",
                reasoning="Boundary check",
            ),
        ]
        mock_llm.structured_query.return_value = PopulationProposal(
            candidates=candidates
        )

        result = await solver.generate_population(
            error_context="IndexError at line 6",
            goal="Fix the bug",
            n=2,
        )

        assert len(result) == 2
        assert result[0].hypothesis == "Fix range"
        assert result[1].hypothesis == "Add check"
        mock_llm.structured_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_candidates(self, solver):
        """Test candidate evaluation."""
        candidates = [
            CodeCandidate(
                hypothesis="Valid code",
                code_patch="print('hello')",
                reasoning="Should work",
            ),
            CodeCandidate(
                hypothesis="Syntax error",
                code_patch="def hello(\n    pass",  # Syntax error
                reasoning="Won't work",
            ),
        ]

        results = await solver.evaluate_candidates(
            candidates=candidates,
            original_code="",
            test_code=None,
            verbose=0,
        )

        # Should be sorted by score (highest first)
        assert len(results) == 2
        assert results[0][1] > results[1][1]  # First has higher score
        assert results[0][0].hypothesis == "Valid code"

    @pytest.mark.asyncio
    async def test_mutate(self, solver, mock_llm):
        """Test candidate mutation."""
        original = CodeCandidate(
            hypothesis="Original",
            code_patch="def add(a, b):\n    return a - b",
            reasoning="Wrong",
        )

        mutated = CodeCandidate(
            hypothesis="Mutated",
            code_patch="def add(a, b):\n    return a + b",
            reasoning="Fixed",
        )

        mock_llm.structured_query.return_value = mutated

        result = await solver.mutate(
            candidate=original,
            fitness_report="Correctness: FAIL",
            verbose=0,
        )

        assert result is not None
        assert result.hypothesis == "Mutated"
        mock_llm.structured_query.assert_called_once()


"""Unit tests for CodeEvaluator."""

import pytest
from cognitive_hydraulics.engine.evaluator import CodeEvaluator, EvaluationResult


class TestCodeEvaluator:
    """Test CodeEvaluator functionality."""

    def test_syntax_validation_valid(self):
        """Test that valid Python syntax passes."""
        evaluator = CodeEvaluator()
        code = "def hello():\n    print('world')"

        result = evaluator._check_syntax(code)
        assert result[0] is True
        assert result[1] is None

    def test_syntax_validation_invalid(self):
        """Test that invalid Python syntax fails."""
        evaluator = CodeEvaluator()
        code = "def hello(\n    print('world')"  # Missing closing paren

        result = evaluator._check_syntax(code)
        assert result[0] is False
        assert result[1] is not None

    def test_runtime_validation_valid(self):
        """Test that code that runs successfully passes."""
        evaluator = CodeEvaluator()
        code = "print('hello')"

        is_valid, error, output = evaluator._check_runtime(code)
        assert is_valid is True
        assert error is None
        assert output is not None

    def test_runtime_validation_invalid(self):
        """Test that code with runtime errors fails."""
        evaluator = CodeEvaluator()
        code = "x = undefined_variable"  # NameError

        is_valid, error, output = evaluator._check_runtime(code)
        assert is_valid is False
        assert error is not None

    def test_correctness_validation_passes(self):
        """Test that code passing tests gets correctness=True."""
        evaluator = CodeEvaluator()
        code = "def add(a, b):\n    return a + b"
        test_code = """
def test_add():
    assert add(2, 3) == 5
    print("All tests passed")

if __name__ == "__main__":
    test_add()
"""

        is_valid, error, output = evaluator._check_correctness(code, test_code)
        assert is_valid is True
        assert error is None
        assert "All tests passed" in output

    def test_correctness_validation_fails(self):
        """Test that code failing tests gets correctness=False."""
        evaluator = CodeEvaluator()
        code = "def add(a, b):\n    return a - b"  # Wrong operation
        test_code = """
def test_add():
    assert add(2, 3) == 5
    print("All tests passed")

if __name__ == "__main__":
    test_add()
"""

        is_valid, error, output = evaluator._check_correctness(code, test_code)
        assert is_valid is False
        assert error is not None

    def test_evaluate_syntax_error(self):
        """Test evaluation of code with syntax error."""
        evaluator = CodeEvaluator()
        code = "def hello(\n    pass"  # Syntax error

        result = evaluator.evaluate(code)
        assert result.score == 0
        assert result.syntax_valid is False
        assert result.runtime_valid is False
        assert result.correctness_valid is False
        assert result.error_message is not None

    def test_evaluate_runtime_error(self):
        """Test evaluation of code with runtime error."""
        evaluator = CodeEvaluator()
        code = "x = undefined_variable"  # NameError

        result = evaluator.evaluate(code)
        assert result.score > 0  # Some score for runtime error
        assert result.score < 40  # But less than correctness failure
        assert result.syntax_valid is True
        assert result.runtime_valid is False
        assert result.correctness_valid is False

    def test_evaluate_runs_but_fails_tests(self):
        """Test evaluation of code that runs but fails tests."""
        evaluator = CodeEvaluator()
        code = "def add(a, b):\n    return a - b"  # Wrong
        test_code = """
def test_add():
    assert add(2, 3) == 5
    print("All tests passed")

if __name__ == "__main__":
    test_add()
"""

        result = evaluator.evaluate(code, test_code=test_code)
        assert result.score >= 40  # Partial credit
        assert result.score < 100  # Not perfect
        assert result.syntax_valid is True
        assert result.runtime_valid is True
        assert result.correctness_valid is False

    def test_evaluate_perfect_score(self):
        """Test evaluation of code that passes all tests."""
        evaluator = CodeEvaluator()
        code = "def add(a, b):\n    return a + b"
        test_code = """
def test_add():
    assert add(2, 3) == 5
    print("All tests passed")

if __name__ == "__main__":
    test_add()
"""

        result = evaluator.evaluate(code, test_code=test_code)
        assert result.score == 100
        assert result.syntax_valid is True
        assert result.runtime_valid is True
        assert result.correctness_valid is True

    def test_score_runtime_error(self):
        """Test scoring of different runtime error types."""
        evaluator = CodeEvaluator()

        # NameError should get higher score than generic error
        name_error_score = evaluator._score_runtime_error("NameError: name 'x' is not defined")
        generic_score = evaluator._score_runtime_error("Some random error")

        assert name_error_score > generic_score
        assert 10 <= name_error_score <= 30
        assert 10 <= generic_score <= 30


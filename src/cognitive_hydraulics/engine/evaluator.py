"""Code evaluator for evolutionary strategy fitness function."""

from __future__ import annotations

import ast
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class EvaluationResult:
    """Result of evaluating a code candidate."""

    score: int  # 0-100
    syntax_valid: bool
    runtime_valid: bool
    correctness_valid: bool
    error_message: Optional[str] = None
    output: Optional[str] = None


class CodeEvaluator:
    """
    Evaluates code candidates for the evolutionary solver.

    Checks:
    1. Syntax validity (AST parsing)
    2. Runtime validity (execution without exceptions)
    3. Correctness (test execution and passing)
    """

    def __init__(self, timeout: float = 10.0):
        """
        Initialize code evaluator.

        Args:
            timeout: Timeout for code execution in seconds
        """
        self.timeout = timeout

    def evaluate(
        self, code: str, test_code: Optional[str] = None
    ) -> EvaluationResult:
        """
        Evaluate a code candidate.

        Args:
            code: The code to evaluate
            test_code: Optional test code to run (if None, checks only syntax/runtime)

        Returns:
            EvaluationResult with score and validation flags
        """
        # Step 1: Syntax check
        syntax_valid, syntax_error = self._check_syntax(code)
        if not syntax_valid:
            return EvaluationResult(
                score=0,
                syntax_valid=False,
                runtime_valid=False,
                correctness_valid=False,
                error_message=f"Syntax error: {syntax_error}",
            )

        # Step 2: Runtime check
        runtime_valid, runtime_error, output = self._check_runtime(code)
        if not runtime_valid:
            # Score based on error type
            score = self._score_runtime_error(runtime_error)
            return EvaluationResult(
                score=score,
                syntax_valid=True,
                runtime_valid=False,
                correctness_valid=False,
                error_message=runtime_error,
                output=output,
            )

        # Step 3: Correctness check (if tests provided)
        if test_code:
            correctness_valid, correctness_error, test_output = self._check_correctness(
                code, test_code
            )
            if correctness_valid:
                return EvaluationResult(
                    score=100,
                    syntax_valid=True,
                    runtime_valid=True,
                    correctness_valid=True,
                    output=test_output,
                )
            else:
                # Runs but fails tests - partial credit
                score = 40  # Base score for running but failing tests
                # Could adjust based on how close it is, but for now use fixed score
                return EvaluationResult(
                    score=score,
                    syntax_valid=True,
                    runtime_valid=True,
                    correctness_valid=False,
                    error_message=correctness_error,
                    output=test_output,
                )
        else:
            # No tests - just check that it runs
            return EvaluationResult(
                score=60,  # Partial credit for running without tests
                syntax_valid=True,
                runtime_valid=True,
                correctness_valid=False,  # Can't verify without tests
                output=output,
            )

    def _check_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Check if code has valid Python syntax.

        Returns:
            (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _check_runtime(
        self, code: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if code runs without exceptions.

        Returns:
            (is_valid, error_message, output)
        """
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    ["python3", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                output = result.stdout if result.stdout else None
                error = result.stderr if result.stderr else None

                if result.returncode == 0:
                    return True, None, output
                else:
                    return False, error or "Unknown runtime error", output

            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            return False, f"Execution timeout ({self.timeout}s)", None
        except Exception as e:
            return False, f"Execution error: {str(e)}", None

    def _check_correctness(
        self, code: str, test_code: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Check if code passes tests.

        Returns:
            (is_valid, error_message, output)
        """
        # Combine code and test code
        full_code = f"{code}\n\n{test_code}"

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(full_code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    ["python3", temp_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                output = result.stdout if result.stdout else None
                error = result.stderr if result.stderr else None

                # Check if tests passed
                if result.returncode == 0:
                    # Check for "All tests passed" in output
                    if output and "All tests passed" in output:
                        return True, None, output
                    else:
                        # Code ran but tests didn't pass (or no test output)
                        return False, "Tests did not pass", output
                else:
                    # Check for AssertionError in stderr
                    if error and "AssertionError" in error:
                        return False, error, output
                    else:
                        # Other runtime error during test execution
                        return False, error or "Test execution failed", output

            finally:
                # Clean up temp file
                Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            return False, f"Test execution timeout ({self.timeout}s)", None
        except Exception as e:
            return False, f"Test execution error: {str(e)}", None

    def _score_runtime_error(self, error: Optional[str]) -> int:
        """
        Score a runtime error (10-30 range).

        Args:
            error: Error message

        Returns:
            Score between 10-30
        """
        if not error:
            return 10

        error_lower = error.lower()

        # More specific errors get higher scores (closer to working)
        if "NameError" in error or "AttributeError" in error:
            return 20  # Missing name/attribute - closer to working
        elif "TypeError" in error:
            return 25  # Type mismatch - very close
        elif "IndexError" in error or "KeyError" in error:
            return 15  # Index/key issue
        elif "ValueError" in error:
            return 20  # Value issue
        else:
            return 10  # Generic error


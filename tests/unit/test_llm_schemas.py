"""Unit tests for LLM schemas."""

import pytest
from pydantic import ValidationError

from cognitive_hydraulics.llm.schemas import (
    OperatorSuggestion,
    OperatorProposal,
    UtilityEstimate,
    UtilityEvaluation,
)


class TestOperatorSuggestion:
    """Tests for OperatorSuggestion schema."""

    def test_create_valid_suggestion(self):
        """Test creating a valid operator suggestion."""
        suggestion = OperatorSuggestion(
            name="read_file",
            parameters={"path": "main.py"},
            reasoning="Need to understand the code",
        )

        assert suggestion.name == "read_file"
        assert suggestion.parameters["path"] == "main.py"
        assert "understand" in suggestion.reasoning

    def test_suggestion_requires_all_fields(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError):
            OperatorSuggestion(name="read_file")  # Missing fields

    def test_suggestion_to_dict(self):
        """Test serialization to dict."""
        suggestion = OperatorSuggestion(
            name="read_file",
            parameters={"path": "test.py"},
            reasoning="Testing",
        )

        data = suggestion.model_dump()

        assert data["name"] == "read_file"
        assert data["parameters"] == {"path": "test.py"}


class TestOperatorProposal:
    """Tests for OperatorProposal schema."""

    def test_create_valid_proposal(self):
        """Test creating a valid operator proposal."""
        proposal = OperatorProposal(
            operators=[
                OperatorSuggestion(
                    name="read_file",
                    parameters={"path": "main.py"},
                    reasoning="Check the code",
                ),
                OperatorSuggestion(
                    name="list_dir",
                    parameters={"path": "."},
                    reasoning="Explore files",
                ),
            ],
            reasoning="Need to understand the codebase",
        )

        assert len(proposal.operators) == 2
        assert proposal.operators[0].name == "read_file"
        assert "understand" in proposal.reasoning

    def test_proposal_min_operators(self):
        """Test that at least 1 operator is required."""
        with pytest.raises(ValidationError):
            OperatorProposal(operators=[], reasoning="Empty")

    def test_proposal_max_operators(self):
        """Test that maximum 5 operators are allowed."""
        with pytest.raises(ValidationError):
            OperatorProposal(
                operators=[
                    OperatorSuggestion(
                        name=f"op{i}", parameters={}, reasoning="Test"
                    )
                    for i in range(6)  # 6 operators - too many
                ],
                reasoning="Too many",
            )


class TestUtilityEstimate:
    """Tests for UtilityEstimate schema."""

    def test_create_valid_estimate(self):
        """Test creating a valid utility estimate."""
        estimate = UtilityEstimate(
            operator_name="read_file(main.py)",
            probability_of_success=0.8,
            estimated_cost=2.5,
            reasoning="Simple file read operation",
        )

        assert estimate.operator_name == "read_file(main.py)"
        assert estimate.probability_of_success == 0.8
        assert estimate.estimated_cost == 2.5

    def test_probability_bounds(self):
        """Test that probability is bounded 0-1."""
        # Valid
        UtilityEstimate(
            operator_name="test",
            probability_of_success=0.0,
            estimated_cost=5.0,
            reasoning="Test",
        )
        UtilityEstimate(
            operator_name="test",
            probability_of_success=1.0,
            estimated_cost=5.0,
            reasoning="Test",
        )

        # Invalid - too low
        with pytest.raises(ValidationError):
            UtilityEstimate(
                operator_name="test",
                probability_of_success=-0.1,
                estimated_cost=5.0,
                reasoning="Test",
            )

        # Invalid - too high
        with pytest.raises(ValidationError):
            UtilityEstimate(
                operator_name="test",
                probability_of_success=1.1,
                estimated_cost=5.0,
                reasoning="Test",
            )

    def test_cost_bounds(self):
        """Test that cost is bounded 1-10."""
        # Valid
        UtilityEstimate(
            operator_name="test",
            probability_of_success=0.5,
            estimated_cost=1.0,
            reasoning="Test",
        )
        UtilityEstimate(
            operator_name="test",
            probability_of_success=0.5,
            estimated_cost=10.0,
            reasoning="Test",
        )

        # Invalid - too low
        with pytest.raises(ValidationError):
            UtilityEstimate(
                operator_name="test",
                probability_of_success=0.5,
                estimated_cost=0.5,
                reasoning="Test",
            )

        # Invalid - too high
        with pytest.raises(ValidationError):
            UtilityEstimate(
                operator_name="test",
                probability_of_success=0.5,
                estimated_cost=11.0,
                reasoning="Test",
            )


class TestUtilityEvaluation:
    """Tests for UtilityEvaluation schema."""

    def test_create_valid_evaluation(self):
        """Test creating a valid utility evaluation."""
        evaluation = UtilityEvaluation(
            evaluations=[
                UtilityEstimate(
                    operator_name="op1",
                    probability_of_success=0.8,
                    estimated_cost=3.0,
                    reasoning="High success, low cost",
                ),
                UtilityEstimate(
                    operator_name="op2",
                    probability_of_success=0.5,
                    estimated_cost=7.0,
                    reasoning="Medium success, high cost",
                ),
            ],
            recommendation="Choose op1 due to better utility",
        )

        assert len(evaluation.evaluations) == 2
        assert "op1" in evaluation.recommendation

    def test_evaluation_requires_estimates(self):
        """Test that at least one estimate is required."""
        with pytest.raises(ValidationError):
            UtilityEvaluation(evaluations=[], recommendation="Empty")

    def test_evaluation_from_json(self):
        """Test parsing from JSON (simulating LLM response)."""
        json_data = {
            "evaluations": [
                {
                    "operator_name": "read_file(test.py)",
                    "probability_of_success": 0.9,
                    "estimated_cost": 2.0,
                    "reasoning": "Quick file read",
                }
            ],
            "recommendation": "Read the file",
        }

        evaluation = UtilityEvaluation.model_validate(json_data)

        assert len(evaluation.evaluations) == 1
        assert evaluation.evaluations[0].probability_of_success == 0.9


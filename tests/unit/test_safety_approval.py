"""Unit tests for human approval system."""

import pytest
from cognitive_hydraulics.safety.approval import (
    HumanApprovalSystem,
    ApprovalRequest,
    ApprovalResult,
    ApprovalDecision,
)
from cognitive_hydraulics.core.state import EditorState
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpWriteFile


class TestApprovalRequest:
    """Tests for ApprovalRequest model."""

    def test_create_approval_request(self):
        """Test creating an approval request."""
        operator = OpReadFile("test.py")
        state = EditorState()

        request = ApprovalRequest(
            operator=operator,
            state=state,
            utility=5.5,
            reasoning="File needs inspection",
        )

        assert request.operator == operator
        assert request.state == state
        assert request.utility == 5.5
        assert request.reasoning == "File needs inspection"

    def test_format_for_display(self):
        """Test formatting request for display."""
        operator = OpWriteFile("output.txt", "content")
        state = EditorState(working_directory="/project")

        request = ApprovalRequest(
            operator=operator,
            state=state,
            utility=2.5,
            reasoning="Writing output file",
        )

        formatted = request.format_for_display()

        assert "APPROVAL REQUIRED" in formatted
        assert "output.txt" in formatted
        assert "DESTRUCTIVE: YES" in formatted
        assert "UTILITY SCORE: 2.50" in formatted
        assert "Writing output file" in formatted
        assert "/project" in formatted


class TestApprovalResult:
    """Tests for ApprovalResult model."""

    def test_create_approved_result(self):
        """Test creating approved result."""
        result = ApprovalResult(decision=ApprovalDecision.APPROVED)

        assert result.decision == ApprovalDecision.APPROVED
        assert result.modified_operator is None
        assert result.feedback is None

    def test_create_rejected_result(self):
        """Test creating rejected result."""
        result = ApprovalResult(
            decision=ApprovalDecision.REJECTED,
            feedback="Too risky",
        )

        assert result.decision == ApprovalDecision.REJECTED
        assert result.feedback == "Too risky"


class TestHumanApprovalSystem:
    """Tests for HumanApprovalSystem."""

    def test_create_approval_system(self):
        """Test creating approval system."""
        system = HumanApprovalSystem(auto_approve_safe=True)

        assert system.auto_approve_safe is True
        assert len(system.approval_history) == 0

    def test_auto_approve_safe_operators(self):
        """Test that safe operators are auto-approved."""
        system = HumanApprovalSystem(auto_approve_safe=True)
        operator = OpReadFile("test.py")  # Not destructive
        state = EditorState()

        result = system.request_approval(operator, state)

        assert result.decision == ApprovalDecision.APPROVED
        assert len(system.approval_history) == 1

    def test_no_auto_approve_when_disabled(self):
        """Test that auto-approve can be disabled."""
        system = HumanApprovalSystem(auto_approve_safe=False)

        # With auto_approve_safe=False, even safe ops need approval
        # But we can't test interactive approval in unit tests
        # So just verify the system was created with correct config
        assert system.auto_approve_safe is False

    def test_approval_rate_empty_history(self):
        """Test approval rate with no history."""
        system = HumanApprovalSystem()

        assert system.get_approval_rate() == 1.0

    def test_approval_rate_calculation(self):
        """Test approval rate calculation."""
        system = HumanApprovalSystem(auto_approve_safe=True)
        state = EditorState()

        # Auto-approve 3 safe operators
        for i in range(3):
            system.request_approval(OpReadFile(f"test{i}.py"), state)

        assert system.get_approval_rate() == 1.0

    def test_get_stats_empty(self):
        """Test stats with empty history."""
        system = HumanApprovalSystem()

        stats = system.get_stats()

        assert stats["total"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0
        assert stats["approval_rate"] == 1.0

    def test_get_stats_with_history(self):
        """Test stats with approval history."""
        system = HumanApprovalSystem(auto_approve_safe=True)
        state = EditorState()

        # Auto-approve 5 safe operators
        for i in range(5):
            system.request_approval(OpReadFile(f"test{i}.py"), state)

        stats = system.get_stats()

        assert stats["total"] == 5
        assert stats["approved"] == 5
        assert stats["rejected"] == 0
        assert stats["approval_rate"] == 1.0

    def test_repr(self):
        """Test string representation."""
        system = HumanApprovalSystem(auto_approve_safe=True)

        repr_str = repr(system)

        assert "HumanApprovalSystem" in repr_str
        assert "auto_approve_safe=True" in repr_str
        assert "requests=0" in repr_str


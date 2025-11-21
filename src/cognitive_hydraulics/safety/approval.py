"""Human approval system for destructive operations."""

from __future__ import annotations

from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field

from cognitive_hydraulics.core.operator import Operator
from cognitive_hydraulics.core.state import EditorState


class ApprovalDecision(str, Enum):
    """Human approval decision."""

    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ApprovalRequest(BaseModel):
    """Request for human approval of an operator."""

    model_config = {"arbitrary_types_allowed": True}

    operator: Operator
    state: EditorState
    utility: Optional[float] = Field(default=None, description="ACT-R utility score")
    reasoning: Optional[str] = Field(
        default=None, description="Why this operator was selected"
    )

    def format_for_display(self) -> str:
        """Format approval request for human display."""
        lines = [
            "═══════════════════════════════════════════════════════════",
            "🚨 APPROVAL REQUIRED",
            "═══════════════════════════════════════════════════════════",
            "",
            f"OPERATOR: {self.operator.name}",
            f"DESTRUCTIVE: {'YES' if self.operator.is_destructive else 'NO'}",
        ]

        if self.utility is not None:
            lines.append(f"UTILITY SCORE: {self.utility:.2f}")

        if self.reasoning:
            lines.append(f"\nREASONING:\n{self.reasoning}")

        lines.extend(
            [
                "",
                "OPERATOR DETAILS:",
                f"  {self.operator}",
                "",
                "CURRENT STATE:",
                f"- Working Directory: {self.state.working_directory}",
                f"- Open Files: {len(self.state.open_files)}",
            ]
        )

        if self.state.error_log:
            lines.append(f"- Recent Errors: {self.state.error_log[-1]}")

        lines.extend(
            [
                "",
                "═══════════════════════════════════════════════════════════",
                "OPTIONS:",
                "  [a] Approve    - Execute this operator",
                "  [r] Reject     - Skip this operator",
                "  [m] Modify     - Change parameters (not yet implemented)",
                "  [q] Quit       - Stop agent execution",
                "═══════════════════════════════════════════════════════════",
            ]
        )

        return "\n".join(lines)


class ApprovalResult(BaseModel):
    """Result of human approval."""

    model_config = {"arbitrary_types_allowed": True}

    decision: ApprovalDecision
    modified_operator: Optional[Operator] = None
    feedback: Optional[str] = None


class HumanApprovalSystem:
    """
    System for requesting human approval for destructive operations.

    Provides a clear interface for humans to approve/reject/modify operators
    before they execute.
    """

    def __init__(self, auto_approve_safe: bool = True):
        """
        Initialize approval system.

        Args:
            auto_approve_safe: If True, automatically approve non-destructive ops
        """
        self.auto_approve_safe = auto_approve_safe
        self.approval_history: list[tuple[ApprovalRequest, ApprovalResult]] = []

    def request_approval(
        self,
        operator: Operator,
        state: EditorState,
        utility: Optional[float] = None,
        reasoning: Optional[str] = None,
    ) -> ApprovalResult:
        """
        Request human approval for an operator.

        Args:
            operator: Operator to approve
            state: Current state
            utility: Optional utility score
            reasoning: Optional reasoning for selection

        Returns:
            ApprovalResult with decision
        """
        # Auto-approve safe operators if configured
        if self.auto_approve_safe and not operator.is_destructive:
            result = ApprovalResult(decision=ApprovalDecision.APPROVED)
            self._record(operator, state, utility, reasoning, result)
            return result

        # Create request
        request = ApprovalRequest(
            operator=operator,
            state=state,
            utility=utility,
            reasoning=reasoning,
        )

        # Display to human
        print("\n" + request.format_for_display())

        # Get input
        while True:
            choice = input("\nYour choice [a/r/m/q]: ").strip().lower()

            if choice == "a":
                result = ApprovalResult(decision=ApprovalDecision.APPROVED)
                break
            elif choice == "r":
                result = ApprovalResult(
                    decision=ApprovalDecision.REJECTED,
                    feedback="Rejected by user",
                )
                break
            elif choice == "m":
                print("⚠️  Operator modification not yet implemented.")
                print("    Please use [a] to approve or [r] to reject.")
                continue
            elif choice == "q":
                print("🛑 Agent execution stopped by user.")
                raise KeyboardInterrupt("User requested stop")
            else:
                print("❌ Invalid choice. Please enter a, r, m, or q.")
                continue

        self._record(operator, state, utility, reasoning, result)
        return result

    def _record(
        self,
        operator: Operator,
        state: EditorState,
        utility: Optional[float],
        reasoning: Optional[str],
        result: ApprovalResult,
    ):
        """Record approval decision in history."""
        request = ApprovalRequest(
            operator=operator,
            state=state,
            utility=utility,
            reasoning=reasoning,
        )
        self.approval_history.append((request, result))

    def get_approval_rate(self) -> float:
        """
        Get approval rate (approved / total).

        Returns:
            Approval rate 0.0-1.0
        """
        if not self.approval_history:
            return 1.0

        approved = sum(
            1
            for _, result in self.approval_history
            if result.decision == ApprovalDecision.APPROVED
        )
        return approved / len(self.approval_history)

    def get_stats(self) -> dict:
        """Get approval statistics."""
        if not self.approval_history:
            return {
                "total": 0,
                "approved": 0,
                "rejected": 0,
                "modified": 0,
                "approval_rate": 1.0,
            }

        approved = sum(
            1
            for _, r in self.approval_history
            if r.decision == ApprovalDecision.APPROVED
        )
        rejected = sum(
            1
            for _, r in self.approval_history
            if r.decision == ApprovalDecision.REJECTED
        )
        modified = sum(
            1
            for _, r in self.approval_history
            if r.decision == ApprovalDecision.MODIFIED
        )

        return {
            "total": len(self.approval_history),
            "approved": approved,
            "rejected": rejected,
            "modified": modified,
            "approval_rate": approved / len(self.approval_history),
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"HumanApprovalSystem(auto_approve_safe={self.auto_approve_safe}, "
            f"requests={stats['total']}, approval_rate={stats['approval_rate']:.2%})"
        )


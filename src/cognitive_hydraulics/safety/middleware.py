"""Safety middleware for operator execution."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.state import EditorState
from cognitive_hydraulics.safety.approval import (
    HumanApprovalSystem,
    ApprovalDecision,
)


class SafetyConfig(BaseModel):
    """Configuration for safety middleware."""

    require_approval_for_destructive: bool = Field(
        default=True,
        description="Require human approval for destructive operations",
    )
    require_approval_below_utility: Optional[float] = Field(
        default=3.0,
        description="Require approval if utility score is below this threshold",
    )
    auto_approve_safe: bool = Field(
        default=True,
        description="Automatically approve non-destructive operations",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, operators don't actually execute (simulation mode)",
    )


class SafetyMiddleware:
    """
    Middleware that wraps operator execution with safety checks.

    Enforces:
    1. Human approval for destructive operations
    2. Human approval for low-utility operations
    3. Dry-run mode (simulate without executing)
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        """
        Initialize safety middleware.

        Args:
            config: Safety configuration (uses defaults if None)
        """
        self.config = config or SafetyConfig()
        self.approval_system = HumanApprovalSystem(
            auto_approve_safe=self.config.auto_approve_safe
        )

    async def execute_with_safety(
        self,
        operator: Operator,
        state: EditorState,
        utility: Optional[float] = None,
        reasoning: Optional[str] = None,
        verbose: bool = True,
    ) -> OperatorResult:
        """
        Execute operator with safety checks.

        Args:
            operator: Operator to execute
            state: Current state
            utility: Optional utility score
            reasoning: Optional reasoning for selection
            verbose: Print status messages

        Returns:
            OperatorResult from execution or simulated result
        """
        # Check 1: Dry-run mode
        if self.config.dry_run:
            if verbose:
                print(f"   🔍 DRY-RUN: Would execute {operator.name}")
            return OperatorResult(
                success=True,
                new_state=state,
                output=f"Dry-run: {operator.name} (not actually executed)",
            )

        # Check 2: Does this need approval?
        needs_approval = self._needs_approval(operator, utility)

        if needs_approval:
            if verbose:
                print(f"   🚨 {operator.name} requires human approval")

            # Request approval
            approval_result = self.approval_system.request_approval(
                operator=operator,
                state=state,
                utility=utility,
                reasoning=reasoning,
            )

            if approval_result.decision == ApprovalDecision.REJECTED:
                if verbose:
                    print(f"   ✗ {operator.name} rejected by user")
                return OperatorResult(
                    success=False,
                    new_state=state,
                    output="",
                    error=f"Rejected by user: {approval_result.feedback or 'No reason given'}",
                )

            if approval_result.decision == ApprovalDecision.MODIFIED:
                # Use modified operator (if implemented)
                operator = approval_result.modified_operator or operator

            # APPROVED - proceed with execution

        # Execute the operator
        if verbose:
            print(f"   ▶ Executing {operator.name}")

        result = await operator.execute(state)

        if verbose:
            if result.success:
                print(f"   ✓ {operator.name} succeeded")
            else:
                print(f"   ✗ {operator.name} failed: {result.message}")

        return result

    def _needs_approval(self, operator: Operator, utility: Optional[float]) -> bool:
        """
        Determine if operator needs human approval.

        Args:
            operator: Operator to check
            utility: Optional utility score

        Returns:
            True if approval required
        """
        # Check 1: Destructive operations
        if self.config.require_approval_for_destructive and operator.is_destructive:
            return True

        # Check 2: Low utility score
        if (
            self.config.require_approval_below_utility is not None
            and utility is not None
            and utility < self.config.require_approval_below_utility
        ):
            return True

        return False

    def enable_dry_run(self):
        """Enable dry-run mode (simulate without executing)."""
        self.config.dry_run = True

    def disable_dry_run(self):
        """Disable dry-run mode (execute normally)."""
        self.config.dry_run = False

    def get_stats(self) -> dict:
        """Get approval statistics."""
        return self.approval_system.get_stats()

    def __repr__(self) -> str:
        return f"SafetyMiddleware(dry_run={self.config.dry_run}, {self.approval_system})"


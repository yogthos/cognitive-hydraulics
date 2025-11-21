"""Unit tests for safety middleware."""

import pytest
from cognitive_hydraulics.safety.middleware import SafetyMiddleware, SafetyConfig
from cognitive_hydraulics.safety.approval import ApprovalDecision
from cognitive_hydraulics.core.state import EditorState, FileContent
from cognitive_hydraulics.core.operator import OperatorResult
from cognitive_hydraulics.operators.file_ops import OpReadFile, OpWriteFile

# Rebuild models at module import to resolve forward references
OperatorResult.model_rebuild()


class TestSafetyConfig:
    """Tests for SafetyConfig model."""

    def test_default_config(self):
        """Test default safety configuration."""
        config = SafetyConfig()

        assert config.require_approval_for_destructive is True
        assert config.require_approval_below_utility == 3.0
        assert config.auto_approve_safe is True
        assert config.dry_run is False

    def test_custom_config(self):
        """Test custom safety configuration."""
        config = SafetyConfig(
            require_approval_for_destructive=False,
            require_approval_below_utility=5.0,
            auto_approve_safe=False,
            dry_run=True,
        )

        assert config.require_approval_for_destructive is False
        assert config.require_approval_below_utility == 5.0
        assert config.auto_approve_safe is False
        assert config.dry_run is True


class TestSafetyMiddleware:
    """Tests for SafetyMiddleware."""

    def test_create_middleware(self):
        """Test creating safety middleware."""
        middleware = SafetyMiddleware()

        assert middleware.config is not None
        assert middleware.approval_system is not None

    def test_create_middleware_with_config(self):
        """Test creating middleware with custom config."""
        config = SafetyConfig(dry_run=True)
        middleware = SafetyMiddleware(config)

        assert middleware.config.dry_run is True

    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test that dry-run mode doesn't execute operators."""
        config = SafetyConfig(dry_run=True)
        middleware = SafetyMiddleware(config)

        operator = OpWriteFile("test.txt", "content")  # Destructive
        state = EditorState()

        result = await middleware.execute_with_safety(
            operator, state, utility=5.0, verbose=False
        )

        assert result.success is True
        assert "Dry-run" in result.output
        assert "not actually executed" in result.output

    @pytest.mark.asyncio
    async def test_safe_operator_auto_approved(self):
        """Test that safe operators are auto-approved."""
        middleware = SafetyMiddleware()

        operator = OpReadFile("test.py")  # Not destructive
        state = EditorState(working_directory="/tmp")

        result = await middleware.execute_with_safety(
            operator, state, utility=5.0, verbose=False
        )

        # Should have been auto-approved and executed
        # (will fail because file doesn't exist, but that's expected)
        assert result.success is False  # File doesn't exist
        error_msg = (result.error or "").lower()
        assert "not found" in error_msg or "no such file" in error_msg

    def test_needs_approval_destructive(self):
        """Test that destructive operators need approval."""
        middleware = SafetyMiddleware()

        operator = OpWriteFile("test.txt", "content")  # Destructive

        assert middleware._needs_approval(operator, utility=5.0) is True

    def test_needs_approval_low_utility(self):
        """Test that low-utility operators need approval."""
        middleware = SafetyMiddleware()

        operator = OpReadFile("test.py")  # Not destructive

        # Below threshold (default 3.0)
        assert middleware._needs_approval(operator, utility=2.0) is True

        # Above threshold
        assert middleware._needs_approval(operator, utility=5.0) is False

    def test_needs_approval_no_utility_threshold(self):
        """Test approval when utility threshold is disabled."""
        config = SafetyConfig(require_approval_below_utility=None)
        middleware = SafetyMiddleware(config)

        operator = OpReadFile("test.py")

        # Should not need approval (not destructive, no utility threshold)
        assert middleware._needs_approval(operator, utility=0.5) is False

    def test_enable_disable_dry_run(self):
        """Test enabling/disabling dry-run mode."""
        middleware = SafetyMiddleware()

        assert middleware.config.dry_run is False

        middleware.enable_dry_run()
        assert middleware.config.dry_run is True

        middleware.disable_dry_run()
        assert middleware.config.dry_run is False

    def test_get_stats(self):
        """Test getting approval statistics."""
        middleware = SafetyMiddleware()

        stats = middleware.get_stats()

        assert stats["total"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0

    def test_repr(self):
        """Test string representation."""
        middleware = SafetyMiddleware()

        repr_str = repr(middleware)

        assert "SafetyMiddleware" in repr_str
        assert "dry_run=" in repr_str


class TestSafetyIntegration:
    """Integration tests for safety system."""

    @pytest.mark.asyncio
    async def test_safe_read_operations_no_approval_needed(self):
        """Test that safe read operations work without approval."""
        middleware = SafetyMiddleware()
        state = EditorState(working_directory="/tmp")

        # Create a temp file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_path = f.name

        try:
            operator = OpReadFile(temp_path)

            result = await middleware.execute_with_safety(
                operator, state, utility=5.0, verbose=False
            )

            assert result.success is True
            assert len(result.new_state.open_files) == 1
        finally:
            import os
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_dry_run_prevents_file_modification(self):
        """Test that dry-run prevents actual file modification."""
        config = SafetyConfig(dry_run=True)
        middleware = SafetyMiddleware(config)
        state = EditorState()

        import tempfile
        import os
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.txt")

        try:
            operator = OpWriteFile(test_file, "content")

            result = await middleware.execute_with_safety(
                operator, state, verbose=False
            )

            assert result.success is True
            assert "Dry-run" in result.output
            assert not os.path.exists(test_file)  # File should not be created
        finally:
            import shutil
            shutil.rmtree(temp_dir)


"""Unit tests for verbosity system."""

import pytest

from cognitive_hydraulics.core.verbosity import (
    VerbosityLevel,
    should_print,
    normalize_verbose,
    format_thinking,
)


class TestVerbosityLevel:
    """Tests for VerbosityLevel enum."""

    def test_verbosity_levels(self):
        """Test verbosity level values."""
        assert VerbosityLevel.SILENT == 0
        assert VerbosityLevel.BASIC == 1
        assert VerbosityLevel.THINKING == 2
        assert VerbosityLevel.DEBUG == 3

    def test_verbosity_level_comparison(self):
        """Test that verbosity levels can be compared."""
        assert VerbosityLevel.THINKING > VerbosityLevel.BASIC
        assert VerbosityLevel.DEBUG >= VerbosityLevel.THINKING
        assert VerbosityLevel.SILENT < VerbosityLevel.BASIC


class TestShouldPrint:
    """Tests for should_print function."""

    def test_should_print_at_exact_level(self):
        """Test printing at exact required level."""
        assert should_print(VerbosityLevel.THINKING, VerbosityLevel.THINKING) is True

    def test_should_print_above_level(self):
        """Test printing above required level."""
        assert should_print(VerbosityLevel.DEBUG, VerbosityLevel.THINKING) is True

    def test_should_not_print_below_level(self):
        """Test not printing below required level."""
        assert should_print(VerbosityLevel.BASIC, VerbosityLevel.THINKING) is False

    def test_should_not_print_silent(self):
        """Test that silent level never prints."""
        assert should_print(VerbosityLevel.SILENT, VerbosityLevel.BASIC) is False


class TestNormalizeVerbose:
    """Tests for normalize_verbose function."""

    def test_normalize_bool_true(self):
        """Test normalizing True to thinking level."""
        assert normalize_verbose(True) == VerbosityLevel.THINKING

    def test_normalize_bool_false(self):
        """Test normalizing False to silent level."""
        assert normalize_verbose(False) == VerbosityLevel.SILENT

    def test_normalize_int(self):
        """Test normalizing int values."""
        assert normalize_verbose(0) == 0
        assert normalize_verbose(1) == 1
        assert normalize_verbose(2) == 2
        assert normalize_verbose(3) == 3

    def test_normalize_backward_compatibility(self):
        """Test backward compatibility with bool values."""
        # True should map to thinking (2), False to silent (0)
        assert normalize_verbose(True) == 2
        assert normalize_verbose(False) == 0


class TestFormatThinking:
    """Tests for format_thinking function."""

    def test_format_thinking_basic(self):
        """Test basic thinking output formatting."""
        result = format_thinking("Test Section", "Line 1\nLine 2")

        assert "THINKING: Test Section" in result
        assert "→ Line 1" in result
        assert "→ Line 2" in result

    def test_format_thinking_multiline(self):
        """Test formatting with multiple lines."""
        content = "First line\nSecond line\nThird line"
        result = format_thinking("Analysis", content)

        lines = result.split("\n")
        assert lines[0] == "THINKING: Analysis"
        assert "→ First line" in lines
        assert "→ Second line" in lines
        assert "→ Third line" in lines

    def test_format_thinking_empty_lines_ignored(self):
        """Test that empty lines are ignored."""
        content = "Line 1\n\nLine 2\n  \nLine 3"
        result = format_thinking("Test", content)

        # Should not have empty arrow lines
        assert "→" in result
        assert result.count("→") == 3  # Only 3 non-empty lines

    def test_format_thinking_strips_whitespace(self):
        """Test that whitespace is stripped from lines."""
        content = "  Line 1  \n  Line 2  "
        result = format_thinking("Test", content)

        assert "→ Line 1" in result
        assert "→ Line 2" in result
        assert "  Line 1  " not in result  # Whitespace should be stripped


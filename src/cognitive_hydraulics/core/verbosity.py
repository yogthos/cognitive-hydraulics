"""Verbosity level system for controlling output detail."""

from __future__ import annotations

from enum import IntEnum
from typing import Union


class VerbosityLevel(IntEnum):
    """Verbosity levels for system output."""

    SILENT = 0  # No output except errors
    BASIC = 1  # Minimal output (current default behavior)
    THINKING = 2  # Shows reasoning and decision-making (default)
    DEBUG = 3  # Detailed trace with all internal state


def should_print(level: int, min_level: int) -> bool:
    """
    Check if output should be printed at given verbosity level.

    Args:
        level: Current verbosity level
        min_level: Minimum level required to print

    Returns:
        True if should print, False otherwise
    """
    return level >= min_level


def normalize_verbose(verbose: Union[bool, int]) -> int:
    """
    Normalize verbose parameter to int.

    Args:
        verbose: Either bool or int verbosity level

    Returns:
        int verbosity level (0-3)
    """
    if isinstance(verbose, bool):
        # Backward compatibility: True -> 2 (thinking), False -> 0 (silent)
        return VerbosityLevel.THINKING if verbose else VerbosityLevel.SILENT
    return int(verbose)


def format_thinking(header: str, content: str, level: int = 2) -> str:
    """
    Format thinking output with structured sections.

    Args:
        header: Section header (e.g., "Analyzing Current State")
        content: Multi-line content with reasoning
        level: Verbosity level (for future formatting options)

    Returns:
        Formatted string with thinking output
    """
    lines = content.strip().split("\n")
    formatted_lines = [f"THINKING: {header}"]
    for line in lines:
        if line.strip():
            formatted_lines.append(f"  → {line.strip()}")
    return "\n".join(formatted_lines)


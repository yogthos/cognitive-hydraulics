"""Context window management for compressing state for LLMs."""

from __future__ import annotations

from typing import Dict, List, Optional
from cognitive_hydraulics.core.state import EditorState, Goal, FileContent
from cognitive_hydraulics.utils.tree_sitter_utils import CodeAnalyzer


class ContextWindowManager:
    """
    Manages LLM context to fit within token limits.

    Intelligently compresses EditorState by:
    1. Including only relevant code sections
    2. Using tree-sitter to extract specific functions/classes
    3. Prioritizing error locations
    4. Summarizing large files
    """

    def __init__(self, max_tokens: int = 4096, chars_per_token: float = 4.0):
        """
        Initialize context manager.

        Args:
            max_tokens: Maximum context window size in tokens
            chars_per_token: Approximate characters per token (default ~4 for code)
        """
        self.max_tokens = max_tokens
        self.chars_per_token = chars_per_token
        self.max_chars = int(max_tokens * chars_per_token)
        self.code_analyzer = CodeAnalyzer()

    def compress_state(self, state: EditorState, goal: Goal) -> Dict:
        """
        Compress state to fit within context window.

        Strategy:
        1. Always include goal description
        2. Always include last error (if exists)
        3. Extract only relevant code sections
        4. Prioritize files mentioned in goal or errors
        5. Use tree-sitter to extract specific functions/classes

        Args:
            state: Current editor state
            goal: Current goal

        Returns:
            Compressed state as dictionary
        """
        compressed = {
            "goal": goal.description,
            "working_directory": state.working_directory,
            "error": state.error_log[-1] if state.error_log else None,
            "relevant_code": {},
            "file_summary": {},
        }

        # Calculate budget for code sections
        base_size = len(str(compressed))
        remaining_chars = self.max_chars - base_size

        # Determine file relevance
        file_priorities = self._calculate_file_priorities(state, goal)

        # Add files in priority order
        for file_path, priority in sorted(
            file_priorities.items(), key=lambda x: x[1], reverse=True
        ):
            if remaining_chars <= 0:
                break

            file_content = state.open_files.get(file_path)
            if not file_content:
                continue

            # Extract relevant section
            relevant_section = self._extract_relevant_section(
                file_content, goal, state, remaining_chars
            )

            if relevant_section:
                compressed["relevant_code"][file_path] = relevant_section
                remaining_chars -= len(relevant_section)
            else:
                # If file too large, provide summary
                summary = self._summarize_file(file_content)
                compressed["file_summary"][file_path] = summary
                remaining_chars -= len(summary)

        return compressed

    def _calculate_file_priorities(
        self, state: EditorState, goal: Goal
    ) -> Dict[str, float]:
        """
        Calculate priority scores for each open file.

        Higher priority = more relevant to current goal/error.

        Args:
            state: Current editor state
            goal: Current goal

        Returns:
            Dict mapping file path to priority score (0.0 - 10.0)
        """
        priorities = {}

        for file_path in state.open_files.keys():
            score = 1.0  # Base score

            # Boost if file mentioned in goal
            if file_path in goal.description:
                score += 5.0

            # Boost if file mentioned in recent errors
            for error in state.error_log[-3:]:
                if file_path in error:
                    score += 3.0

            # Boost if file was recently modified (if we have cursor position)
            if file_path in state.cursor_position:
                score += 2.0

            priorities[file_path] = score

        return priorities

    def _extract_relevant_section(
        self,
        file_content: FileContent,
        goal: Goal,
        state: EditorState,
        max_chars: int,
    ) -> Optional[str]:
        """
        Extract the most relevant section of a file.

        Uses tree-sitter to intelligently extract:
        - Function mentioned in goal/error
        - Lines around error location
        - Entire file if small enough

        Args:
            file_content: File to extract from
            goal: Current goal
            state: Current state (for error info)
            max_chars: Maximum characters to extract

        Returns:
            Relevant code section or None
        """
        code = file_content.content

        # If file is small enough, return whole thing
        if len(code) <= max_chars:
            return code

        # Try to parse with tree-sitter
        tree = self.code_analyzer.parse_code(code, file_content.language)
        if not tree:
            # Fallback: return first N lines
            return self._truncate_to_lines(code, max_chars)

        # Look for function/class mentioned in goal
        functions = self.code_analyzer.find_functions(tree, file_content.language)
        for func in functions:
            if func["name"] in goal.description:
                # Extract this function
                start = func["start_byte"]
                end = func["end_byte"]
                func_code = code[start:end]
                if len(func_code) <= max_chars:
                    return self._add_context_marker(
                        func_code, f"Function: {func['name']}"
                    )

        # Look for error line if mentioned in errors
        if state.error_log:
            last_error = state.error_log[-1]
            # Try to extract line number from error message
            import re

            match = re.search(r"line (\d+)", last_error)
            if match:
                error_line = int(match.group(1)) - 1  # Convert to 0-indexed
                node = self.code_analyzer.find_node_at_line(tree, error_line)
                if node:
                    # Extract the containing function/class
                    node_code = code[node.start_byte : node.end_byte]
                    if len(node_code) <= max_chars:
                        return self._add_context_marker(
                            node_code, f"Around line {error_line + 1}"
                        )

        # Fallback: return file summary
        return self._truncate_to_lines(code, max_chars)

    def _truncate_to_lines(self, code: str, max_chars: int) -> str:
        """Truncate code to approximately max_chars, preserving line boundaries."""
        lines = code.split("\n")
        result_lines = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > max_chars:
                result_lines.append("... (truncated)")
                break
            result_lines.append(line)
            current_length += line_length

        return "\n".join(result_lines)

    def _add_context_marker(self, code: str, marker: str) -> str:
        """Add a context marker at the beginning of code."""
        return f"# {marker}\n{code}"

    def _summarize_file(self, file_content: FileContent) -> str:
        """
        Create a summary of a file when it's too large to include.

        Args:
            file_content: File to summarize

        Returns:
            Summary string
        """
        tree = self.code_analyzer.parse_code(file_content.content, file_content.language)
        if not tree:
            # Fallback: basic info
            line_count = len(file_content.content.split("\n"))
            return f"<{file_content.language} file, {line_count} lines>"

        # Extract structure
        functions = self.code_analyzer.find_functions(tree, file_content.language)
        classes = self.code_analyzer.find_classes(tree, file_content.language)
        imports = self.code_analyzer.get_imports(tree, file_content.language)

        summary_parts = [f"<{file_content.language} file>"]

        if imports:
            summary_parts.append(f"Imports: {len(imports)}")

        if classes:
            class_names = [c["name"] for c in classes[:5]]  # First 5
            summary_parts.append(f"Classes: {', '.join(class_names)}")
            if len(classes) > 5:
                summary_parts.append(f"... and {len(classes) - 5} more")

        if functions:
            func_names = [f["name"] for f in functions[:5]]  # First 5
            summary_parts.append(f"Functions: {', '.join(func_names)}")
            if len(functions) > 5:
                summary_parts.append(f"... and {len(functions) - 5} more")

        return " | ".join(summary_parts)

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a piece of text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return int(len(text) / self.chars_per_token)


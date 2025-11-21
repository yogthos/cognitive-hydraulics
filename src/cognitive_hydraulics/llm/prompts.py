"""Prompt templates for LLM interactions."""

from __future__ import annotations

from typing import Dict, List


class PromptTemplates:
    """Structured prompts for different reasoning modes."""

    # System prompt used for all LLM interactions
    SYSTEM_PROMPT = """You are a reasoning assistant in a cognitive architecture.
You must respond with ONLY valid JSON matching the provided schema.
Be concise, precise, and actionable. Focus on concrete steps that can be executed."""

    @staticmethod
    def generate_operators_prompt(
        state_summary: Dict, goal: str, error: str = None
    ) -> str:
        """
        Prompt for NO_CHANGE impasse: Generate new operator proposals.

        Used when the rule engine has no applicable rules.

        Args:
            state_summary: Compressed state from ContextWindowManager
            goal: Goal description
            error: Recent error if available

        Returns:
            Prompt string
        """
        parts = [
            f"GOAL: {goal}",
            "",
            "CURRENT STATE:",
            f"- Working directory: {state_summary.get('working_directory', '.')}",
            f"- Open files: {state_summary.get('open_files', [])}",
        ]

        if error:
            parts.extend(["", f"RECENT ERROR: {error}"])

        # Add relevant code if available
        relevant_code = state_summary.get("relevant_code", {})
        if relevant_code:
            parts.append("")
            parts.append("RELEVANT CODE:")
            for filepath, code in list(relevant_code.items())[:2]:  # Limit to 2 files
                parts.append(f"\n{filepath}:")
                parts.append(f"```\n{code[:500]}\n```")  # Truncate long code

        parts.extend(
            [
                "",
                "The symbolic reasoning system has no applicable rules for this situation.",
                "Suggest 2-3 concrete operators that could make progress toward the goal.",
                "",
                "Available operator types:",
                "- read_file: Read a file (parameters: {'path': 'filename'})",
                "- list_dir: List directory contents (parameters: {'path': 'dirname'})",
                "",
                "IMPORTANT: You must respond with valid JSON matching this exact schema:",
                "{",
                '  "operators": [',
                '    {',
                '      "name": "read_file",',
                '      "parameters": {"path": "example.py"},',
                '      "reasoning": "Need to read the file to analyze it"',
                "    }",
                "  ],",
                '  "reasoning": "Overall explanation of why these operators help"',
                "}",
                "",
                "Each operator must have:",
                "- 'name': The operator name (e.g., 'read_file', 'list_dir')",
                "- 'parameters': A dictionary with operator-specific parameters",
                "- 'reasoning': Why this operator might help",
                "",
                "The response must also include a top-level 'reasoning' field.",
            ]
        )

        return "\n".join(parts)

    @staticmethod
    def evaluate_utilities_prompt(
        state_summary: Dict,
        goal: str,
        operators: List[str],
        goal_value: float = 10.0,
    ) -> str:
        """
        Prompt for TIE impasse: Rate multiple operators.

        Used when multiple operators have equal priority.

        Args:
            state_summary: Compressed state
            goal: Goal description
            operators: List of operator names to evaluate
            goal_value: Value of achieving the goal (for context)

        Returns:
            Prompt string
        """
        parts = [
            f"GOAL: {goal}",
            f"GOAL VALUE: {goal_value} (higher = more important)",
            "",
            "CURRENT STATE:",
            f"- Working directory: {state_summary.get('working_directory', '.')}",
            f"- Open files: {state_summary.get('open_files', [])}",
        ]

        error = state_summary.get("error")
        if error:
            parts.extend(["", f"RECENT ERROR: {error}"])

        parts.extend(
            [
                "",
                "CANDIDATE OPERATORS:",
            ]
        )
        for i, op in enumerate(operators, 1):
            parts.append(f"{i}. {op}")

        parts.extend(
            [
                "",
                "For EACH operator, estimate:",
                "1. Probability of Success (0.0-1.0): How likely will this advance the goal?",
                "2. Estimated Cost (1-10): How expensive/time-consuming is this?",
                "   - 1-3: Quick operations (read file, list dir)",
                "   - 4-7: Medium operations (search, parse)",
                "   - 8-10: Expensive operations (compile, test suite)",
                "",
                "The utility formula is: U = P * G - C",
                f"Where G = {goal_value} (goal value)",
                "",
                "IMPORTANT: You must respond with valid JSON matching this exact schema:",
                "{",
                '  "evaluations": [',
                '    {',
                '      "operator_name": "read_file(sort.py)",',
                '      "probability_of_success": 0.8,',
                '      "estimated_cost": 2.0,',
                '      "reasoning": "Reading the file is quick and will reveal the code structure"',
                "    }",
                "  ],",
                '  "recommendation": "read_file(sort.py) is recommended because..."',
                "}",
                "",
                "Each evaluation must have:",
                "- 'operator_name': The exact operator name as provided",
                "- 'probability_of_success': A float between 0.0 and 1.0",
                "- 'estimated_cost': A float between 1.0 and 10.0",
                "- 'reasoning': Explanation for the estimates",
                "",
                "The response must also include a 'recommendation' field explaining which operator is best.",
            ]
        )

        return "\n".join(parts)

    @staticmethod
    def compress_prompt_if_needed(prompt: str, max_length: int = 3000) -> str:
        """
        Compress a prompt if it's too long.

        Args:
            prompt: The prompt to potentially compress
            max_length: Maximum allowed length

        Returns:
            Original or compressed prompt
        """
        if len(prompt) <= max_length:
            return prompt

        # Simple compression: truncate code sections
        lines = prompt.split("\n")
        compressed_lines = []
        in_code_block = False
        code_lines_kept = 0

        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                code_lines_kept = 0
                compressed_lines.append(line)
            elif in_code_block:
                if code_lines_kept < 10:  # Keep first 10 lines of code
                    compressed_lines.append(line)
                    code_lines_kept += 1
                elif code_lines_kept == 10:
                    compressed_lines.append("... (truncated)")
                    code_lines_kept += 1
            else:
                compressed_lines.append(line)

        return "\n".join(compressed_lines)


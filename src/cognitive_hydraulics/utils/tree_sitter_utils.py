"""Tree-sitter utilities for multi-language code analysis."""

from __future__ import annotations

from typing import Optional, Dict, List, Any
from dataclasses import dataclass

import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_rust
import tree_sitter_go


@dataclass
class ParsedNode:
    """Represents a parsed AST node with useful metadata."""

    type: str
    text: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    children: List[ParsedNode]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
            "children": [child.to_dict() for child in self.children],
        }


class CodeAnalyzer:
    """Multi-language code analyzer using tree-sitter."""

    def __init__(self):
        """Initialize parsers for all supported languages."""
        self.parsers: Dict[str, tree_sitter.Parser] = {}
        self._init_parsers()

    def _init_parsers(self) -> None:
        """Initialize tree-sitter parsers for supported languages."""
        # Python
        python_parser = tree_sitter.Parser()
        python_parser.language = tree_sitter.Language(tree_sitter_python.language())
        self.parsers["python"] = python_parser

        # JavaScript
        js_parser = tree_sitter.Parser()
        js_parser.language = tree_sitter.Language(tree_sitter_javascript.language())
        self.parsers["javascript"] = js_parser

        # TypeScript
        ts_parser = tree_sitter.Parser()
        ts_parser.language = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        self.parsers["typescript"] = ts_parser

        # Rust
        rust_parser = tree_sitter.Parser()
        rust_parser.language = tree_sitter.Language(tree_sitter_rust.language())
        self.parsers["rust"] = rust_parser

        # Go
        go_parser = tree_sitter.Parser()
        go_parser.language = tree_sitter.Language(tree_sitter_go.language())
        self.parsers["go"] = go_parser

    def supported_languages(self) -> List[str]:
        """Return list of supported languages."""
        return list(self.parsers.keys())

    def parse_code(self, code: str, language: str) -> Optional[tree_sitter.Tree]:
        """
        Parse code into a tree-sitter AST.

        Args:
            code: Source code to parse
            language: Programming language (python, javascript, typescript, rust, go)

        Returns:
            Parsed tree or None if language unsupported
        """
        parser = self.parsers.get(language)
        if not parser:
            return None

        return parser.parse(bytes(code, "utf8"))

    def serialize_tree(self, tree: tree_sitter.Tree, source_code: str) -> Dict[str, Any]:
        """
        Serialize a tree-sitter tree to a dictionary.

        Args:
            tree: Parsed tree-sitter tree
            source_code: Original source code (for extracting text)

        Returns:
            Serialized tree as nested dict
        """
        source_bytes = bytes(source_code, "utf8")
        return self._serialize_node(tree.root_node, source_bytes)

    def _serialize_node(
        self, node: tree_sitter.Node, source_bytes: bytes
    ) -> Dict[str, Any]:
        """Recursively serialize a tree-sitter node."""
        return {
            "type": node.type,
            "start_line": node.start_point[0],
            "end_line": node.end_point[0],
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
            "text": source_bytes[node.start_byte : node.end_byte].decode("utf8"),
            "children": [self._serialize_node(child, source_bytes) for child in node.children],
        }

    def find_functions(self, tree: tree_sitter.Tree, language: str) -> List[Dict[str, Any]]:
        """
        Extract all function definitions from the tree.

        Args:
            tree: Parsed tree-sitter tree
            language: Programming language

        Returns:
            List of function definitions with metadata
        """
        function_types = {
            "python": ["function_definition"],
            "javascript": ["function_declaration", "arrow_function", "function"],
            "typescript": ["function_declaration", "arrow_function", "function"],
            "rust": ["function_item"],
            "go": ["function_declaration"],
        }

        target_types = function_types.get(language, [])
        functions = []

        def traverse(node: tree_sitter.Node):
            if node.type in target_types:
                # Try to extract function name
                name_node = None
                for child in node.children:
                    if child.type in ["identifier", "name"]:
                        name_node = child
                        break

                functions.append(
                    {
                        "type": node.type,
                        "name": name_node.text.decode("utf8") if name_node else "<anonymous>",
                        "start_line": node.start_point[0],
                        "end_line": node.end_point[0],
                        "start_byte": node.start_byte,
                        "end_byte": node.end_byte,
                    }
                )

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return functions

    def find_classes(self, tree: tree_sitter.Tree, language: str) -> List[Dict[str, Any]]:
        """
        Extract all class definitions from the tree.

        Args:
            tree: Parsed tree-sitter tree
            language: Programming language

        Returns:
            List of class definitions with metadata
        """
        class_types = {
            "python": ["class_definition"],
            "javascript": ["class_declaration"],
            "typescript": ["class_declaration"],
            "rust": ["struct_item", "enum_item", "impl_item"],
            "go": ["type_declaration"],
        }

        target_types = class_types.get(language, [])
        classes = []

        def traverse(node: tree_sitter.Node):
            if node.type in target_types:
                # Try to extract class name
                name_node = None
                for child in node.children:
                    if child.type in ["identifier", "type_identifier", "name"]:
                        name_node = child
                        break

                classes.append(
                    {
                        "type": node.type,
                        "name": name_node.text.decode("utf8") if name_node else "<anonymous>",
                        "start_line": node.start_point[0],
                        "end_line": node.end_point[0],
                        "start_byte": node.start_byte,
                        "end_byte": node.end_byte,
                    }
                )

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return classes

    def extract_function_body(
        self, code: str, function_name: str, language: str
    ) -> Optional[str]:
        """
        Extract the body of a specific function by name.

        Args:
            code: Source code
            function_name: Name of the function to extract
            language: Programming language

        Returns:
            Function body as string, or None if not found
        """
        tree = self.parse_code(code, language)
        if not tree:
            return None

        functions = self.find_functions(tree, language)
        for func in functions:
            if func["name"] == function_name:
                start = func["start_byte"]
                end = func["end_byte"]
                return code[start:end]

        return None

    def get_imports(self, tree: tree_sitter.Tree, language: str) -> List[str]:
        """
        Extract all import statements from the tree.

        Args:
            tree: Parsed tree-sitter tree
            language: Programming language

        Returns:
            List of import statements as strings
        """
        import_types = {
            "python": ["import_statement", "import_from_statement"],
            "javascript": ["import_statement"],
            "typescript": ["import_statement"],
            "rust": ["use_declaration"],
            "go": ["import_declaration"],
        }

        target_types = import_types.get(language, [])
        imports = []

        def traverse(node: tree_sitter.Node):
            if node.type in target_types:
                imports.append(node.text.decode("utf8"))

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)
        return imports

    def find_node_at_line(
        self, tree: tree_sitter.Tree, line_number: int
    ) -> Optional[tree_sitter.Node]:
        """
        Find the deepest AST node that contains the given line.

        Useful for finding the syntactic context of an error.

        Args:
            tree: Parsed tree-sitter tree
            line_number: Line number (0-indexed)

        Returns:
            Node containing the line, or None
        """

        def find_deepest(node: tree_sitter.Node) -> Optional[tree_sitter.Node]:
            start_line = node.start_point[0]
            end_line = node.end_point[0]

            if not (start_line <= line_number <= end_line):
                return None

            # Check children first (to find deepest)
            for child in node.children:
                result = find_deepest(child)
                if result:
                    return result

            # If no child contains it, this node is the deepest
            return node

        return find_deepest(tree.root_node)


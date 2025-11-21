"""Unit tests for tree-sitter utilities."""

import pytest
from cognitive_hydraulics.utils.tree_sitter_utils import CodeAnalyzer


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer."""

    def test_initialize_analyzer(self):
        """Test that analyzer initializes with all languages."""
        analyzer = CodeAnalyzer()
        languages = analyzer.supported_languages()

        assert "python" in languages
        assert "javascript" in languages
        assert "typescript" in languages
        assert "rust" in languages
        assert "go" in languages
        assert len(languages) == 5

    def test_parse_python_code(self):
        """Test parsing simple Python code."""
        analyzer = CodeAnalyzer()
        code = "def hello():\n    print('world')"

        tree = analyzer.parse_code(code, "python")

        assert tree is not None
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    def test_parse_javascript_code(self):
        """Test parsing simple JavaScript code."""
        analyzer = CodeAnalyzer()
        code = "function hello() { console.log('world'); }"

        tree = analyzer.parse_code(code, "javascript")

        assert tree is not None
        assert tree.root_node is not None

    def test_parse_unsupported_language(self):
        """Test parsing with unsupported language returns None."""
        analyzer = CodeAnalyzer()
        code = "some code"

        tree = analyzer.parse_code(code, "unsupported")

        assert tree is None

    def test_serialize_tree(self):
        """Test serializing a parsed tree to dict."""
        analyzer = CodeAnalyzer()
        code = "x = 1"

        tree = analyzer.parse_code(code, "python")
        serialized = analyzer.serialize_tree(tree, code)

        assert isinstance(serialized, dict)
        assert "type" in serialized
        assert "children" in serialized
        assert serialized["type"] == "module"

    def test_find_functions_python(self):
        """Test finding functions in Python code."""
        analyzer = CodeAnalyzer()
        code = """
def function_one():
    pass

def function_two(x, y):
    return x + y

class MyClass:
    def method_one(self):
        pass
"""

        tree = analyzer.parse_code(code, "python")
        functions = analyzer.find_functions(tree, "python")

        # Should find 3 functions (2 top-level + 1 method)
        assert len(functions) >= 2  # At least the two top-level
        function_names = [f["name"] for f in functions]
        assert "function_one" in function_names
        assert "function_two" in function_names

    def test_find_functions_javascript(self):
        """Test finding functions in JavaScript code."""
        analyzer = CodeAnalyzer()
        code = """
function regularFunction() {
    return 42;
}

const arrowFunction = () => {
    return 'hello';
};
"""

        tree = analyzer.parse_code(code, "javascript")
        functions = analyzer.find_functions(tree, "javascript")

        assert len(functions) >= 1
        function_names = [f["name"] for f in functions]
        assert "regularFunction" in function_names

    def test_find_classes_python(self):
        """Test finding classes in Python code."""
        analyzer = CodeAnalyzer()
        code = """
class FirstClass:
    pass

class SecondClass:
    def method(self):
        pass
"""

        tree = analyzer.parse_code(code, "python")
        classes = analyzer.find_classes(tree, "python")

        assert len(classes) == 2
        class_names = [c["name"] for c in classes]
        assert "FirstClass" in class_names
        assert "SecondClass" in class_names

    def test_extract_function_body(self):
        """Test extracting a specific function by name."""
        analyzer = CodeAnalyzer()
        code = """
def target_function(x):
    return x * 2

def other_function():
    pass
"""

        extracted = analyzer.extract_function_body(code, "target_function", "python")

        assert extracted is not None
        assert "target_function" in extracted
        assert "x * 2" in extracted
        assert "other_function" not in extracted

    def test_extract_nonexistent_function(self):
        """Test extracting a function that doesn't exist."""
        analyzer = CodeAnalyzer()
        code = "def foo(): pass"

        extracted = analyzer.extract_function_body(code, "nonexistent", "python")

        assert extracted is None

    def test_get_imports_python(self):
        """Test extracting import statements from Python code."""
        analyzer = CodeAnalyzer()
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""

        tree = analyzer.parse_code(code, "python")
        imports = analyzer.get_imports(tree, "python")

        assert len(imports) == 4
        assert any("import os" in imp for imp in imports)
        assert any("from pathlib import Path" in imp for imp in imports)

    def test_get_imports_javascript(self):
        """Test extracting import statements from JavaScript code."""
        analyzer = CodeAnalyzer()
        code = """
import React from 'react';
import { useState } from 'react';
"""

        tree = analyzer.parse_code(code, "javascript")
        imports = analyzer.get_imports(tree, "javascript")

        assert len(imports) >= 1

    def test_find_node_at_line(self):
        """Test finding AST node at a specific line."""
        analyzer = CodeAnalyzer()
        code = """def outer():
    def inner():
        x = 1
        y = 2
        return x + y
    return inner()
"""

        tree = analyzer.parse_code(code, "python")
        # Line 2 (0-indexed) should be inside inner function
        node = analyzer.find_node_at_line(tree, 2)

        assert node is not None
        assert node.start_point[0] <= 2 <= node.end_point[0]

    def test_find_node_at_line_out_of_bounds(self):
        """Test finding node at line that doesn't exist."""
        analyzer = CodeAnalyzer()
        code = "x = 1"

        tree = analyzer.parse_code(code, "python")
        node = analyzer.find_node_at_line(tree, 100)

        # Should still return something (root node) or None
        # depending on implementation
        assert node is None or node == tree.root_node

    def test_parse_rust_code(self):
        """Test parsing Rust code."""
        analyzer = CodeAnalyzer()
        code = """
fn main() {
    println!("Hello, world!");
}
"""

        tree = analyzer.parse_code(code, "rust")

        assert tree is not None
        functions = analyzer.find_functions(tree, "rust")
        assert len(functions) >= 1
        assert any(f["name"] == "main" for f in functions)

    def test_parse_go_code(self):
        """Test parsing Go code."""
        analyzer = CodeAnalyzer()
        code = """
package main

func main() {
    println("Hello, world!")
}
"""

        tree = analyzer.parse_code(code, "go")

        assert tree is not None
        functions = analyzer.find_functions(tree, "go")
        assert len(functions) >= 1

    def test_function_metadata(self):
        """Test that function metadata includes all expected fields."""
        analyzer = CodeAnalyzer()
        code = """
def test_function():
    pass
"""

        tree = analyzer.parse_code(code, "python")
        functions = analyzer.find_functions(tree, "python")

        assert len(functions) == 1
        func = functions[0]
        assert "name" in func
        assert "type" in func
        assert "start_line" in func
        assert "end_line" in func
        assert "start_byte" in func
        assert "end_byte" in func
        assert func["name"] == "test_function"


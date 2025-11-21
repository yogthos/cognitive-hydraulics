"""Smoke tests to verify installation and basic functionality."""

import pytest


def test_imports():
    """Verify all core dependencies can be imported."""
    import cognitive_hydraulics
    import pydantic
    import tree_sitter
    import ollama
    import rich
    import typer

    # Note: chromadb-client has issues with Python 3.14
    # We'll import it at runtime when needed, not at test time
    try:
        import chromadb
    except Exception as e:
        pytest.skip(f"chromadb incompatible with Python 3.14: {e}")

    assert cognitive_hydraulics.__version__ == "0.1.0"


def test_pydantic_models():
    """Verify Pydantic is working correctly."""
    from pydantic import BaseModel, Field

    class TestModel(BaseModel):
        name: str
        value: int = Field(gt=0)

    model = TestModel(name="test", value=42)
    assert model.name == "test"
    assert model.value == 42

    # Should raise validation error
    with pytest.raises(Exception):
        TestModel(name="test", value=-1)


def test_tree_sitter_available():
    """Verify tree-sitter parsers are available."""
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_rust
    import tree_sitter_go

    # All imports should succeed
    assert tree_sitter_python
    assert tree_sitter_javascript
    assert tree_sitter_typescript
    assert tree_sitter_rust
    assert tree_sitter_go


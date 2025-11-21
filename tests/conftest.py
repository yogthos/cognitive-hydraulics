"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with sample files."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()

    # Create a sample Python file with an intentional bug
    sample_file = workspace / "sample.py"
    sample_file.write_text("""
def process_data(items):
    results = []
    for i in range(len(items)):
        # Bug: index out of range on the next line
        results.append(items[i + 1])
    return results

if __name__ == "__main__":
    data = [1, 2, 3, 4, 5]
    print(process_data(data))
""")

    return workspace


@pytest.fixture
def sample_javascript_file(tmp_path: Path) -> Path:
    """Create a sample JavaScript file for multi-language testing."""
    js_file = tmp_path / "sample.js"
    js_file.write_text("""
function calculateTotal(items) {
    let total = 0;
    for (let i = 0; i <= items.length; i++) {
        // Bug: should be i < items.length
        total += items[i];
    }
    return total;
}

module.exports = { calculateTotal };
""")
    return js_file


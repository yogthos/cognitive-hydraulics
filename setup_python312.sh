#!/bin/bash
# Quick setup script for Python 3.12

set -e

echo "=== Setting up Python 3.12 environment ==="
echo ""

# Check Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 not found"
    echo "   Install with: brew install python@3.12"
    exit 1
fi

echo "✓ Python 3.12 found: $(python3.12 --version)"
echo ""

# Remove old venv if it exists
if [ -d "venv" ]; then
    echo "⚠️  Removing existing venv..."
    rm -rf venv
fi

# Create new venv
echo "Creating virtual environment with Python 3.12..."
python3.12 -m venv venv

# Activate
source venv/bin/activate

# Verify version
echo ""
echo "✓ Virtual environment activated"
echo "  Python version: $(python --version)"
echo ""

# Install package
echo "Installing cognitive-hydraulics..."
pip install --upgrade pip --quiet
pip install -e . --quiet

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To activate: source venv/bin/activate"
echo "To run example: python examples/bug_fix_example.py"
echo ""

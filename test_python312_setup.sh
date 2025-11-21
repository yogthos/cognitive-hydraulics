#!/bin/bash
# Quick test script to verify Python 3.12 setup

echo "=== Testing Python 3.12 Setup ==="
echo ""

# Check if Python 3.12 is available
if command -v python3.12 &> /dev/null; then
    echo "✓ Python 3.12 found: $(python3.12 --version)"
else
    echo "✗ Python 3.12 not found"
    echo "  Install with: brew install python@3.12"
    exit 1
fi

# Check if venv exists
if [ -d "venv" ]; then
    echo "⚠️  Existing venv found. Remove it first: rm -rf venv"
    read -p "Remove existing venv? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        echo "✓ Removed existing venv"
    fi
fi

# Create new venv with Python 3.12
echo "Creating venv with Python 3.12..."
python3.12 -m venv venv

# Activate and test
source venv/bin/activate
echo "✓ Virtual environment activated"
echo "  Python version: $(python --version)"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -e . --quiet

# Test ChromaDB
echo ""
echo "Testing ChromaDB..."
python -c "
from cognitive_hydraulics.memory.chroma_store import ChunkStore
from cognitive_hydraulics.memory.chunk import Chunk
from datetime import datetime

store = ChunkStore()
chunk = Chunk(
    id='test',
    state_signature={'goal': 'test'},
    operator_name='test_op',
    operator_params={},
    goal_description='test',
    created_at=datetime.now(),
    last_used=datetime.now(),
)
result = store.store_chunk(chunk)
if result:
    print('✓ ChromaDB working correctly!')
else:
    print('✗ ChromaDB failed')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Setup Complete ==="
    echo "✓ Python 3.12 environment ready"
    echo "✓ ChromaDB working"
    echo ""
    echo "To activate: source venv/bin/activate"
else
    echo ""
    echo "✗ Setup failed"
    exit 1
fi

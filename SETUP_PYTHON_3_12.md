# Setting Up Python 3.12 for Cognitive Hydraulics

This guide shows how to run Cognitive Hydraulics with Python 3.12 to enable full functionality including the learning/chunking system (ChromaDB).

## Quick Setup

### Option 1: Using System Python 3.12 (macOS with Homebrew)

If you have Python 3.12 installed via Homebrew:

```bash
# Navigate to project directory
cd /Users/yogthos/src/cognitive-hydraulics

# Remove existing venv (if you want a fresh start)
rm -rf venv

# Create new venv with Python 3.12
python3.12 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.12.x

# Install dependencies
pip install --upgrade pip
pip install -e .

# Verify ChromaDB works
python -c "from chromadb import Client; print('✓ ChromaDB working!')"
```

### Option 2: Using pyenv

If you use pyenv to manage Python versions:

```bash
# Install Python 3.12 (if not already installed)
pyenv install 3.12.0

# Set local Python version for this project
cd /Users/yogthos/src/cognitive-hydraulics
pyenv local 3.12.0

# Remove existing venv
rm -rf venv

# Create new venv (will use Python 3.12)
python -m venv venv

# Activate
source venv/bin/activate

# Verify version
python --version  # Should show Python 3.12.x

# Install dependencies
pip install --upgrade pip
pip install -e .
```

### Option 3: Using conda

```bash
# Create conda environment with Python 3.12
conda create -n cognitive-hydraulics python=3.12
conda activate cognitive-hydraulics

# Install dependencies
pip install --upgrade pip
pip install -e .
```

## Verify Setup

### 1. Check Python Version

```bash
python --version
# Should output: Python 3.12.x
```

### 2. Test ChromaDB

```bash
python -c "
from cognitive_hydraulics.memory.chroma_store import ChunkStore
from cognitive_hydraulics.memory.chunk import Chunk
from datetime import datetime

store = ChunkStore()
print('✓ ChunkStore created')

# Test storing a chunk
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
print(f'✓ ChromaDB working: {result}')
"
```

Expected output:
```
✓ ChunkStore created
✓ ChromaDB working: True
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Should see: "211 passed, 1 skipped" (the skipped test is for Python 3.14 compatibility)
```

### 4. Test Learning System

```bash
# Run an example with learning enabled
python examples/bug_fix_example.py

# Check that chunks are being learned
python -m cognitive_hydraulics chunks list
```

## Troubleshooting

### Python 3.12 Not Found

**On macOS with Homebrew:**
```bash
brew install python@3.12
```

**On Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3.12 python3.12-venv

# Fedora
sudo dnf install python3.12
```

**Using pyenv:**
```bash
pyenv install 3.12.0
pyenv local 3.12.0
```

### ChromaDB Still Fails

If ChromaDB still doesn't work on Python 3.12:

1. **Check Python version:**
   ```bash
   python --version
   ```

2. **Reinstall ChromaDB:**
   ```bash
   pip uninstall chromadb-client
   pip install chromadb-client
   ```

3. **Check for conflicting packages:**
   ```bash
   pip list | grep -i pydantic
   # Should show pydantic>=2.5.0, not pydantic<2.0
   ```

### Virtual Environment Issues

If you have issues with the virtual environment:

```bash
# Deactivate current environment
deactivate

# Remove old venv
rm -rf venv

# Create fresh venv with Python 3.12
python3.12 -m venv venv
source venv/bin/activate

# Reinstall everything
pip install --upgrade pip
pip install -e .
```

## Switching Between Python Versions

If you need to switch between Python 3.12 and 3.14:

```bash
# For Python 3.12 (full functionality)
python3.12 -m venv venv-3.12
source venv-3.12/bin/activate
pip install -e .

# For Python 3.14 (symbolic-only, no learning)
python3.14 -m venv venv-3.14
source venv-3.14/bin/activate
pip install -e .
```

## Benefits of Python 3.12

- ✅ **Full ChromaDB support** - Learning/chunking system works
- ✅ **All features enabled** - No graceful degradation needed
- ✅ **Better compatibility** - All dependencies work correctly
- ✅ **Production ready** - Stable and well-tested Python version

## Current Status

- **Python 3.10-3.12**: ✅ Full functionality
- **Python 3.13**: ✅ Should work (not fully tested)
- **Python 3.14+**: ⚠️ Symbolic-only mode (learning disabled)

For more details, see [PYTHON_3_14_COMPATIBILITY.md](PYTHON_3_14_COMPATIBILITY.md).


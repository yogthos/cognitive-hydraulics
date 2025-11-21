# Quick Start: Running with Python 3.12

## The Problem

When you run `python3.12 bug_fix_example.py`, you're using the system Python 3.12 which doesn't have the `cognitive_hydraulics` package installed.

## Solution: Create a New Virtual Environment

### Step 1: Create a fresh venv with Python 3.12

```bash
cd /Users/yogthos/src/cognitive-hydraulics

# Option A: Remove old venv and create new one
rm -rf venv
python3.12 -m venv venv

# Option B: Keep old venv, create a new one with different name
python3.12 -m venv venv-3.12
```

### Step 2: Activate the virtual environment

```bash
source venv/bin/activate
# OR if you used venv-3.12:
# source venv-3.12/bin/activate
```

### Step 3: Verify Python version

```bash
python --version
# Should show: Python 3.12.x
```

### Step 4: Install the package

```bash
pip install --upgrade pip
pip install -e .
```

### Step 5: Run the example

```bash
# From the project root
python examples/bug_fix_example.py

# OR from the examples directory
cd examples
python bug_fix_example.py
```

## Alternative: Use the venv's Python directly

If you don't want to activate the venv, you can use it directly:

```bash
# From project root
./venv/bin/python examples/bug_fix_example.py

# OR
venv/bin/python examples/bug_fix_example.py
```

## Verify Installation

```bash
# Check package is installed
python -c "import cognitive_hydraulics; print('✓ Package installed')"

# Check Python version
python --version

# Check ChromaDB works
python -c "from chromadb import Client; print('✓ ChromaDB available')"
```

## Common Issues

### Issue: "ModuleNotFoundError: No module named 'cognitive_hydraulics'"

**Cause**: Package not installed in the Python environment you're using.

**Solution**:
1. Make sure you've activated the venv: `source venv/bin/activate`
2. Install the package: `pip install -e .`
3. Verify: `python -c "import cognitive_hydraulics"`

### Issue: "venv uses Python 3.14 instead of 3.12"

**Cause**: Existing venv was created with Python 3.14.

**Solution**: Create a new venv with Python 3.12:
```bash
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install -e .
```

### Issue: "python3.12 command not found"

**Cause**: Python 3.12 not installed or not in PATH.

**Solution**: Install Python 3.12:
```bash
# macOS with Homebrew
brew install python@3.12

# Then create venv
python3.12 -m venv venv
```

## Quick Command Reference

```bash
# Create and setup Python 3.12 environment
cd /Users/yogthos/src/cognitive-hydraulics
rm -rf venv
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .

# Run example
python examples/bug_fix_example.py

# Deactivate when done
deactivate
```


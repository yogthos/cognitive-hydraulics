# Python 3.14 Compatibility Notes

## ChromaDB Compatibility Issue

### Problem

ChromaDB uses Pydantic V1 internally, which is **not compatible with Python 3.14+**. When running on Python 3.14, you will see:

```
UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
  from pydantic.v1 import BaseSettings
```

And when ChromaDB is actually used (not just imported), it will fail with:

```
ConfigError: unable to infer type for attribute "chroma_server_nofile"
```

### Impact

- **Learning/Chunking system is disabled** on Python 3.14+
- The system will work in "symbolic-only" mode without learning
- All other functionality (Soar reasoning, ACT-R fallback, LLM integration) works normally

### Solutions

#### Option 1: Use Python 3.10, 3.11, or 3.12 (Recommended)

For full functionality including learning, use a supported Python version:

```bash
# Using pyenv
pyenv install 3.12.0
pyenv local 3.12.0

# Create new venv
python -m venv venv
source venv/bin/activate
pip install -e .
```

#### Option 2: Wait for ChromaDB Update

ChromaDB is actively working on migrating to Pydantic V2. Monitor their releases:
- [ChromaDB GitHub Issues](https://github.com/chroma-core/chroma/issues)
- [ChromaDB Releases](https://github.com/chroma-core/chroma/releases)

#### Option 3: Use Symbolic-Only Mode

The system gracefully degrades when ChromaDB is unavailable:
- All reasoning capabilities work
- Only the learning/chunking system is disabled
- No errors or crashes

### Current Status

- ✅ **Warning suppression**: ChromaDB warnings are suppressed at import time
- ✅ **Graceful degradation**: System disables learning if ChromaDB unavailable
- ✅ **Error handling**: Clear error messages when ChromaDB fails
- ⚠️ **Learning disabled**: Chunking system not available on Python 3.14+

### Testing

To verify ChromaDB status:

```python
from cognitive_hydraulics.memory.chroma_store import ChunkStore

try:
    store = ChunkStore()
    # Try to actually use it
    from cognitive_hydraulics.memory.chunk import Chunk
    from datetime import datetime

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
    print(f"✓ ChromaDB working: {result}")
except Exception as e:
    print(f"✗ ChromaDB not available: {e}")
```

### Implementation Details

The system handles ChromaDB failures in two places:

1. **`chroma_store.py`**: Suppresses warnings and provides clear error messages
2. **`cognitive_agent.py`**: Catches initialization failures and disables learning gracefully

```python
# In cognitive_agent.py
if enable_learning:
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
            self.chunk_store = ChunkStore(persist_directory=chunk_store_path)
    except (RuntimeError, Exception) as e:
        self.chunk_store = None
        self.enable_learning = False  # Graceful degradation
```

### References

- [Pydantic V1 Deprecation](https://docs.pydantic.dev/2.12/migration/)
- [ChromaDB GitHub](https://github.com/chroma-core/chroma)
- [Python 3.14 Release Notes](https://docs.python.org/3.14/whatsnew/3.14.html)


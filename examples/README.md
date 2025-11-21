# Examples

This directory contains examples demonstrating the Cognitive Hydraulics architecture.

## Running Examples

### Basic Example
Demonstrates the fundamental Soar decision cycle:

```bash
python examples/basic_example.py
```

**What it shows:**
- Creating a cognitive agent
- Setting up initial state and goal
- Running the Soar decision cycle
- Operator proposal and selection

### Learning Example
Demonstrates the chunking/learning system:

```bash
python examples/learning_example.py
```

**What it shows:**
- First encounter: Slow (ACT-R + LLM)
- Chunk creation after success
- Second encounter: Fast (memory retrieval)
- 10x speedup from learning

### Bug Fix Example
Demonstrates finding and fixing bugs in code:

```bash
python examples/bug_fix_example.py
```

**What it shows:**
- Reading and analyzing buggy code (`sort.py`)
- AST parsing with Tree-sitter
- Identifying the bug (IndexError in bubble sort)
- Suggesting a fix using hybrid reasoning
- The bug: `range(0, n - i)` should be `range(0, n - i - 1)` to avoid index out of bounds

## Example Structure

Each example follows this pattern:

1. **Setup** - Create agent with configuration
2. **Initial State** - Define starting state
3. **Goal** - Specify what to achieve
4. **Execution** - Run the agent
5. **Results** - Show outcomes and statistics

## Key Concepts Demonstrated

### Basic Example
- ✅ Soar decision cycle
- ✅ Rule-based reasoning
- ✅ Operator selection
- ✅ Dry-run mode

### Learning Example
- ✅ ACT-R fallback
- ✅ Chunk creation
- ✅ Memory retrieval
- ✅ Learning from experience

### Bug Fix Example
- ✅ Code analysis with AST parsing
- ✅ Bug detection and identification
- ✅ Fix suggestion generation
- ✅ Real-world debugging scenario

## Configuration Options

All examples support these agent configurations:

```python
agent = CognitiveAgent(
    # Safety
    safety_config=SafetyConfig(
        dry_run=True,  # Simulate without executing
        require_approval_for_destructive=False,
    ),

    # Learning
    enable_learning=True,
    chunk_store_path="./chunks",  # Or None for in-memory

    # Execution
    max_cycles=100,
    depth_threshold=3,
    time_threshold_ms=500.0,
)
```

## Next Steps

After running these examples, explore:

1. **CLI Interface**: `python -m cognitive_hydraulics --help`
2. **Custom Goals**: Modify the examples with your own goals
3. **Real Operations**: Disable dry-run for actual file operations
4. **Learning Persistence**: Use persistent chunk storage

## Architecture Flow

```
State → Propose (Rules + Memory) → Decide → Apply → Learn
         ↓                           ↓
    Check Chunks             Impasse? → ACT-R
         ↓                              ↓
    Found? → Execute           LLM Utility → Select
```

## Safety

All examples run in **dry-run mode** by default, which means:
- ✅ No actual file operations
- ✅ Safe to experiment
- ✅ Shows what *would* happen

To enable real operations, set `dry_run=False` in the SafetyConfig.


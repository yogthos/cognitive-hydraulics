<!-- 9ef7207b-3260-4f78-9c4a-f89ba569a606 7e74f67a-d19f-484a-90b3-7a8e7d7e9807 -->
# Fix LLM Client Timeout and Hanging Issues

## Problem

The system hangs indefinitely when:

1. Ollama server is not running
2. The LLM model is not available
3. LLM takes too long to respond
4. Connection attempts block forever

## Solution Strategy

### 1. Add Proper Timeout Handling to LLM Client

**File: `src/cognitive_hydraulics/llm/client.py`**

- Add connection timeout (2 seconds) before attempting queries
- Add query timeout (60 seconds) for LLM responses
- Use `asyncio.wait_for()` with timeouts on all blocking calls
- Return `None` gracefully on timeouts instead of hanging
- Add verbose error messages to help debugging

### 2. Update Cognitive Agent to Handle LLM Failures

**File: `src/cognitive_hydraulics/engine/cognitive_agent.py`**

- When ACT-R resolver returns `None` (LLM failed), fall back to:
  - Breaking ties by selecting first operator
  - Creating sub-goals for NO_CHANGE impasses
  - Failing gracefully with clear error message
- Add max impasse count to prevent infinite loops
- Track consecutive failures and abort if stuck

### 3. Improve ACTRResolver Error Handling

**File: `src/cognitive_hydraulics/engine/actr_resolver.py`**

- Check if LLM response is `None` before processing
- Return `None` immediately if connection fails
- Add fallback behavior when LLM is unavailable
- Log clear errors about why LLM failed

### 4. Add CLI Warning for Missing Ollama

**File: `src/cognitive_hydraulics/cli/main.py`**

- Check Ollama connection before starting solve
- Show warning if Ollama is not running
- Suggest starting Ollama or using --dry-run mode
- Continue with degraded functionality (no ACT-R)

### 5. Update Examples to Handle Offline Mode

**Files: `examples/bug_fix_example.py`, `examples/basic_example.py`**

- Add try/except around agent execution
- Show helpful error if Ollama is not available
- Suggest checking Ollama status
- Gracefully exit with error code

### 6. Add Integration Test for Offline Mode

**File: `tests/integration/test_offline_mode.py`**

- Test that agent handles missing Ollama gracefully
- Test that system doesn't hang on timeout
- Test that appropriate errors are logged
- Verify fallback behavior works

## Implementation Details

### Connection Check with Timeout

```python
try:
    await asyncio.wait_for(
        asyncio.to_thread(client.list), 
        timeout=2.0
    )
except (asyncio.TimeoutError, Exception):
    return None  # Ollama not available
```

### Query with Timeout

```python
try:
    response = await asyncio.wait_for(
        asyncio.to_thread(client.chat, ...),
        timeout=60.0
    )
except asyncio.TimeoutError:
    return None  # Query timed out
```

### Agent Fallback Logic

```python
if result is None:  # LLM failed
    if impasse.type == ImpasseType.TIE:
        # Fall back to first operator
        operator = impasse.operators[0]
        await self._apply_operator(operator, verbose)
        return True
    else:
        # Cannot proceed without LLM
        return False
```

## Expected Outcome

After implementation:

- System never hangs indefinitely
- Clear error messages when Ollama is unavailable
- Graceful degradation (symbolic reasoning still works)
- Examples exit cleanly with helpful error messages
- Tests verify timeout behavior
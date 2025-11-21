<!-- 9ef7207b-3260-4f78-9c4a-f89ba569a606 52821cb6-fa4a-46de-b881-9c552e5baa64 -->
# Persistent Memory System Implementation

## Overview

Implement a ChromaDB-backed persistent goal stack that enables crash recovery and semantic retrieval of past solutions. This merges the existing ChunkStore with a new OperationalMemory system.

## Phase 1: Create Memory Schema

Create `src/cognitive_hydraulics/memory/context_node.py` with the ContextNode model:

```python
from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4

class ContextNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    parent_id: Optional[str] = None  # None = Root Goal
    goal_description: str
    current_state_snapshot: str
    status: str = "active"  # active, success, failed, paused
    created_at: float
    depth: int = 0
    
    # Optional: Store key operator info for impasse resolutions
    resolution_operator: Optional[str] = None
    resolution_reasoning: Optional[str] = None
```

## Phase 2: Create Unified Memory System

Create `src/cognitive_hydraulics/memory/unified_memory.py` that merges ChunkStore functionality with OperationalMemory:

**Key features:**

- Two ChromaDB collections: "goal_stack" (contexts) and "chunks" (learned rules)
- Goal stack operations: push_context(), pop_context(), get_active_context()
- Semantic retrieval: retrieve_relevant_history() for similar past solutions
- Chunk learning: Migrate existing ChunkStore methods (store_chunk, retrieve_chunks)

**Core methods from memory.md:**

```python
def push_context(self, goal: str, state: str, parent_id: Optional[str] = None) -> str
def pop_context(self, status: str = "success", resolution_op: Optional[str] = None) -> Optional[str]
def get_active_context() -> Optional[dict]
def retrieve_relevant_history(self, query: str, max_results: int = 3) -> List[str]
def get_context_chain() -> List[dict]  # For debugging: full parent chain
```

**Integration strategy:**

- Use existing `_get_client()` pattern from `chroma_store.py`
- Handle Python 3.14+ compatibility gracefully (same error handling)
- Store ContextNode as metadata + embedded text (goal + parent + state)

## Phase 3: Migrate CognitiveAgent to Use UnifiedMemory

Update `src/cognitive_hydraulics/engine/cognitive_agent.py`:

**Changes:**

1. Replace `self.chunk_store = ChunkStore()` with `self.memory = UnifiedMemory()`
2. Keep `self.goal_stack: List[Goal]` for in-memory tracking, but back it with UnifiedMemory
3. Update `_push_goal()`:
   ```python
   def _push_goal(self, goal: Goal) -> None:
       self.goal_stack.append(goal)
       self.current_goal = goal
       # NEW: Persist to memory
       state_snapshot = self._create_state_snapshot(self.working_memory.current_state)
       context_id = self.memory.push_context(
           goal=goal.description,
           state=state_snapshot,
           parent_id=self.current_context_id
       )
       self.current_context_id = context_id
   ```

4. Update `_pop_goal()`:
   ```python
   def _pop_goal(self) -> Optional[Goal]:
       if len(self.goal_stack) > 1:
           old_goal = self.goal_stack.pop()
           self.current_goal = self.goal_stack[-1]
           # NEW: Persist to memory
           status = "success" if old_goal.status == "success" else "failed"
           self.current_context_id = self.memory.pop_context(status=status)
           return self.current_goal
       return None
   ```

5. Store impasse resolutions in memory when ACT-R is used:

   - In `_handle_impasse()`, after ACT-R resolves, call `memory.update_context_resolution()`

## Phase 4: Integrate Semantic Retrieval into ACT-R

Update `src/cognitive_hydraulics/engine/actr_resolver.py`:

**In `generate_operators()` method:**

1. Before querying LLM, retrieve similar past solutions:
   ```python
   # NEW: Check memory for similar past solutions
   if hasattr(self, 'memory') and self.memory:
       similar_solutions = self.memory.retrieve_relevant_history(
           query=error or goal.description,
           max_results=2
       )
       if similar_solutions:
           # Inject into prompt
           context_additions.append("PAST SOLUTIONS:")
           for sol in similar_solutions:
               context_additions.append(f"- {sol}")
   ```

2. Pass this context to `PromptTemplates.generate_operators_prompt()`

**Update prompt template in `src/cognitive_hydraulics/llm/prompts.py`:**

- Add optional `past_solutions: List[str]` parameter
- Inject them into the prompt: "Note: Similar issues were previously resolved using..."

## Phase 5: Add Crash Recovery Support

Update `src/cognitive_hydraulics/cli/main.py`:

**Add --resume flag:**

```python
@app.command()
def solve(
    goal: str,
    # ... existing params ...
    resume: bool = typer.Option(False, "--resume", help="Resume from last active context"),
):
    # NEW: Check for active contexts if --resume
    if resume:
        memory = UnifiedMemory(...)
        active_context = memory.get_active_context()
        if active_context:
            print(f"Resuming from: {active_context['goal_description']}")
            # Reconstruct state from context
            agent.current_context_id = active_context['id']
            agent.goal_stack = [Goal(description=active_context['goal_description'])]
        else:
            print("No active context found to resume")
            return
```

**On crash/interruption:**

- UnifiedMemory persists contexts to disk automatically (ChromaDB handles this)
- Active contexts remain with status="active" until explicitly popped

## Phase 6: Update Existing References

1. Update `src/cognitive_hydraulics/memory/__init__.py`:

   - Export `UnifiedMemory` instead of `ChunkStore`
   - Keep backward compatibility by aliasing: `ChunkStore = UnifiedMemory`

2. Update imports in:

   - `cognitive_agent.py`: Use `UnifiedMemory`
   - Any tests that use `ChunkStore`

3. Update initialization in `cognitive_agent.py`:
   ```python
   if enable_learning:
       self.memory = UnifiedMemory(persist_directory=chunk_store_path)
       self.current_context_id = None
   ```


## Testing Strategy

1. Unit tests for UnifiedMemory:

   - Test push/pop operations
   - Test semantic retrieval
   - Test context chain traversal

2. Integration test for crash recovery:

   - Start solve, interrupt mid-cycle
   - Run with --resume, verify it continues

3. Test semantic retrieval in ACT-R:

   - Create two similar bugs in sequence
   - Verify second bug retrieves solution from first

## Migration Notes

- Existing ChunkStore data remains compatible (same "chunks" collection)
- New "goal_stack" collection created automatically on first use
- Gracefully handle ChromaDB unavailability (Python 3.14+)
- If ChromaDB fails, fall back to in-memory goal stack only

### To-dos

- [ ] Investigate ChromaDB Python 3.14 compatibility issue
- [ ] Add warning suppression for ChromaDB Pydantic V1 warning
- [ ] Add graceful error handling for ChromaDB import failures
- [ ] Document Python 3.14 compatibility limitations
- [ ] Create ContextNode schema in memory/context_node.py
- [ ] Create UnifiedMemory class merging OperationalMemory + ChunkStore
- [ ] Update CognitiveAgent to use UnifiedMemory for goal stack
- [ ] Add semantic retrieval to ACT-R resolver
- [ ] Add --resume flag to CLI for crash recovery
- [ ] Update imports and backward compatibility aliases
- [ ] Add unit and integration tests for memory system
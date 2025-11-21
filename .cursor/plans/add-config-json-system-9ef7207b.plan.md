<!-- 9ef7207b-3260-4f78-9c4a-f89ba569a606 136252c2-c592-49f2-a3d7-5b896344d71b -->
# Evolutionary Strategy Implementation Plan

## Overview

Implement an Evolutionary Strategy (ES) system as a fallback when ACT-R fails or pressure is very high, preventing infinite loops on operators like `read_file` and evolving better solutions through genetic algorithms.

## Phase 1: Tabu Search - History Tracking

### 1.1 Add Action Count Tracking to WorkingMemory

**File:** `src/cognitive_hydraulics/core/working_memory.py`

- Add `action_counts: Dict[str, int] = {}` to track operator usage
- Update `record_transition()` to increment count for each operator name
- Add method `get_action_count(operator_name: str) -> int` to retrieve counts
- Add method `reset_action_counts()` for testing/cleanup

### 1.2 Modify ACT-R Utility Calculation

**File:** `src/cognitive_hydraulics/engine/actr_resolver.py`

- Update `resolve()` method to accept `working_memory: Optional[WorkingMemory] = None`
- Modify utility calculation in the loop (around line 142):
  ```python
  # Get history penalty
  history_penalty = 0.0
  if working_memory:
      action_count = working_memory.get_action_count(op.name)
      history_penalty = action_count * 2.0  # Penalty per attempt
  
  U = P * self.G - C - history_penalty + noise
  ```

- Update call sites in `cognitive_agent.py` to pass `working_memory` to `resolve()`

### 1.3 Update CognitiveAgent Integration

**File:** `src/cognitive_hydraulics/engine/cognitive_agent.py`

- Pass `self.working_memory` to `actr_resolver.resolve()` calls (around lines 343 and 458)

## Phase 2: Code Evaluator

### 2.1 Create CodeEvaluator Class

**File:** `src/cognitive_hydraulics/engine/evaluator.py` (new file)

- Class `CodeEvaluator` with method `evaluate(code: str, test_code: Optional[str] = None) -> EvaluationResult`
- `EvaluationResult` dataclass with:
  - `score: int` (0-100)
  - `syntax_valid: bool`
  - `runtime_valid: bool`
  - `correctness_valid: bool`
  - `error_message: Optional[str]`
  - `output: Optional[str]`
- Implementation:
  - Syntax check: Use `ast.parse()` to validate Python syntax
  - Runtime check: Execute code in subprocess with timeout (10s)
  - Correctness check: If test_code provided, run it and check for "All tests passed"
  - Score calculation:
    - Syntax error: 0
    - Runtime error: 10-30 (depending on error type)
    - Runs but fails tests: 40-60
    - Runs and passes tests: 100

## Phase 3: Evolutionary Solver

### 3.1 Create EvolutionarySolver Class

**File:** `src/cognitive_hydraulics/engine/evolution.py` (new file)

- Class `EvolutionarySolver` with:
  - `__init__(llm_client: LLMClient, evaluator: CodeEvaluator, config: Optional[Config] = None)`
  - `generate_population(error_context: str, goal: str, n: int = 4) -> List[CodeCandidate]`
  - `evaluate_candidates(candidates: List[CodeCandidate], original_code: str) -> List[tuple[CodeCandidate, int]]`
  - `mutate(candidate: CodeCandidate, fitness_report: str) -> CodeCandidate`
  - `evolve(error_context: str, goal: str, original_code: str, generations: int = 3) -> Optional[CodeCandidate]`

### 3.2 CodeCandidate Schema

**File:** `src/cognitive_hydraulics/llm/schemas.py`

- Add `CodeCandidate` Pydantic model:
  ```python
  class CodeCandidate(BaseModel):
      hypothesis: str  # Description of the fix
      code_patch: str  # The actual code change
      reasoning: str   # Why this approach
  ```

- Add `PopulationProposal` schema for LLM response:
  ```python
  class PopulationProposal(BaseModel):
      candidates: List[CodeCandidate]
  ```


### 3.3 LLM Prompts for Evolution

**File:** `src/cognitive_hydraulics/llm/prompts.py`

- Add `generate_population_prompt(error_context: str, goal: str, n: int) -> str`:
  - Prompt LLM to generate `n` distinct hypotheses
  - Emphasize diversity (no repeating `read_file`)
  - Request code patches, not just descriptions
- Add `mutate_candidate_prompt(candidate: CodeCandidate, fitness_report: str) -> str`:
  - Use the guidance template from ga.md
  - Focus on fixing specific failures (syntax/runtime/correctness)

### 3.4 Evolutionary Algorithm Logic

**File:** `src/cognitive_hydraulics/engine/evolution.py`

- `evolve()` method:

  1. Generate initial population (4 candidates)
  2. For each generation (up to 3):

     - Evaluate all candidates
     - If any candidate scores 100, return it
     - Select best candidate
     - Mutate best candidate based on fitness report
     - Add mutated candidate to next generation
     - Generate 3 new diverse candidates to fill population

  1. Return best candidate found (even if < 100)

## Phase 4: Integration with CognitiveAgent

### 4.1 Add Evolutionary Fallback Trigger

**File:** `src/cognitive_hydraulics/engine/cognitive_agent.py`

- Add `EvolutionarySolver` instance to `__init__()` (requires `CodeEvaluator`)
- Modify `_handle_impasse()` method:
  - When pressure >= 0.9 OR when NO_CHANGE impasse persists after ACT-R:
    - Check if goal involves code fixing (keywords: "fix", "bug", "error", "sort")
    - If yes, trigger `EvolutionarySolver.evolve()`
    - Apply winning patch using `OpApplyFix` operator
- Add configuration option `enable_evolution: bool = True` to CognitiveAgent

### 4.2 Error Context Extraction

**File:** `src/cognitive_hydraulics/engine/cognitive_agent.py`

- Add helper method `_extract_error_context(state: EditorState) -> str`:
  - Extract error from `state.error_log`
  - Extract relevant code from open files
  - Format as context string for evolutionary solver

## Phase 5: Testing

### 5.1 Unit Tests

**File:** `tests/unit/test_evaluator.py` (new)

- Test syntax validation
- Test runtime validation
- Test correctness validation
- Test score calculation

**File:** `tests/unit/test_evolution.py` (new)

- Test population generation
- Test candidate evaluation
- Test mutation
- Test evolution loop

**File:** `tests/unit/test_working_memory_action_counts.py` (new)

- Test action count tracking
- Test history penalty calculation

### 5.2 Integration Tests

**File:** `tests/integration/test_evolutionary_fallback.py` (new)

- Test full flow: impasse -> evolution -> fix application
- Test that history penalty prevents loops

## Configuration

### Config Updates

**File:** `src/cognitive_hydraulics/config/settings.py`

- Add optional fields:
  - `evolution_enabled: bool = True`
  - `evolution_population_size: int = 4`
  - `evolution_max_generations: int = 3`
  - `history_penalty_multiplier: float = 2.0`

## Files to Create

1. `src/cognitive_hydraulics/engine/evaluator.py`
2. `src/cognitive_hydraulics/engine/evolution.py`
3. `tests/unit/test_evaluator.py`
4. `tests/unit/test_evolution.py`
5. `tests/unit/test_working_memory_action_counts.py`
6. `tests/integration/test_evolutionary_fallback.py`

## Files to Modify

1. `src/cognitive_hydraulics/core/working_memory.py` - Add action_counts
2. `src/cognitive_hydraulics/engine/actr_resolver.py` - Add history penalty
3. `src/cognitive_hydraulics/engine/cognitive_agent.py` - Integrate evolutionary solver
4. `src/cognitive_hydraulics/llm/schemas.py` - Add CodeCandidate schema
5. `src/cognitive_hydraulics/llm/prompts.py` - Add evolution prompts
6. `src/cognitive_hydraulics/config/settings.py` - Add evolution config

### To-dos

- [ ] Create ContextNode schema in memory/context_node.py
- [ ] Create UnifiedMemory class merging OperationalMemory + ChunkStore
- [ ] Update CognitiveAgent to use UnifiedMemory for goal stack
- [ ] Add semantic retrieval to ACT-R resolver
- [ ] Add --resume flag to CLI for crash recovery
- [ ] Update imports and backward compatibility aliases
- [ ] Add unit and integration tests for memory system
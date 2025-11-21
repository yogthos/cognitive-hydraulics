<!-- 9ef7207b-3260-4f78-9c4a-f89ba569a606 9300d919-4dff-4aa9-9de3-138290cc7ed3 -->
# Add Thinking Output with Configurable Verbosity Levels

## Overview

Enhance the system to print high-level reasoning at each step, showing why operators are chosen, why the system switches between Soar/ACT-R modes, and meta-cognitive reasoning. Add configurable verbosity levels (0=silent, 1=basic, 2=thinking, 3=debug) with level 2 as default.

## Implementation Plan

### 1. Add Verbosity Level System

**File: `src/cognitive_hydraulics/core/verbosity.py` (new)**

- Create `VerbosityLevel` enum with values: SILENT=0, BASIC=1, THINKING=2, DEBUG=3
- Create helper functions:
  - `should_print(level: int, min_level: int) -> bool`
  - `format_thinking(header: str, content: str, level: int) -> str`

### 2. Update CognitiveAgent to Support Verbosity Levels

**File: `src/cognitive_hydraulics/engine/cognitive_agent.py`**

- Change `verbose: bool = True` to `verbose: int = 2` (default to thinking mode)
- Update `solve()` method:
  - Add thinking output for goal analysis
  - Show initial state assessment
- Update `_decision_cycle()` method:
  - Add "THINKING: Analyzing current state..." section
  - Show why rules matched/didn't match (level 2+)
  - Add "THINKING: Evaluating operator proposals..." section
  - Show reasoning for operator selection
- Update `_handle_impasse()` method:
  - Add "THINKING: Impasse detected..." section
  - Show why impasse occurred
  - Add "THINKING: Checking cognitive pressure..." section
  - Show pressure calculation and why fallback is/isn't triggered
  - Add "THINKING: Switching to ACT-R mode..." with reasoning
- Update `_apply_operator()` method:
  - Add "THINKING: Applying operator..." with expected outcome reasoning

### 3. Update RuleEngine to Show Rule Matching Reasoning

**File: `src/cognitive_hydraulics/engine/rule_engine.py`**

- Add `propose_operators_with_reasoning()` method that returns (operator, priority, reason) tuples
- Show which rules fired and why (at verbosity level 2+)
- Show why other rules didn't match (at verbosity level 3)

### 4. Update ACTRResolver to Show Utility Reasoning

**File: `src/cognitive_hydraulics/engine/actr_resolver.py`**

- Update `resolve()` method:
  - Add "THINKING: Calculating utilities..." section
  - Show utility calculation breakdown: U = P×G - C + Noise
  - Show why each operator was rated as it was
- Update `generate_operators()` method:
  - Add "THINKING: Generating operators from LLM..." section
  - Show reasoning for why LLM suggested each operator

### 5. Update MetaCognitiveMonitor to Show Pressure Reasoning

**File: `src/cognitive_hydraulics/engine/meta_monitor.py`**

- Add `get_thinking_summary(metrics: CognitiveMetrics) -> str` method
- Show breakdown of pressure calculation:
  - Depth component
  - Time component
  - Ambiguity component
  - Final pressure value and interpretation

### 6. Update CLI to Support Verbosity Levels

**File: `src/cognitive_hydraulics/cli/main.py`**

- Change `verbose: bool` to `verbose: int = 2` in `solve()` command
- Update help text to explain levels:
  - `0` = Silent (errors only)
  - `1` = Basic (current minimal output)
  - `2` = Thinking (default, shows reasoning)
  - `3` = Debug (detailed trace)
- Add `--quiet` flag that sets verbose=0
- Keep `--verbose` flag but make it set verbose=2 (or increment if already set)

### 7. Update Examples to Use New Verbosity

**Files: `examples/basic_example.py`, `examples/bug_fix_example.py`**

- Update to use `verbose=2` (thinking mode) by default
- Show examples of different verbosity levels in comments

### 8. Add Thinking Output Format

**Format Structure:**

```
THINKING: [Section Name]
  → [Reasoning line 1]
  → [Reasoning line 2]
  → [Decision/Conclusion]
```

**Example Output:**

```
THINKING: Analyzing Current State
  → Working directory: /project
  → Open files: main.py (200 lines)
  → Recent error: None
  → Goal: Fix bug in main.py

THINKING: Evaluating Operator Proposals
  → Rule "read_file" matched: file mentioned in goal
  → Rule "analyze_code" matched: file already open
  → Selected: analyze_code (priority: 7.0)
  → Reasoning: File is open, can analyze immediately

THINKING: Checking Cognitive Pressure
  → Depth: 0/3 (CALM)
  → Time in state: 50ms (CALM)
  → Ambiguity: 0.2 (LOW)
  → Pressure: 0.15 (CALM - continuing with Soar)
```

## Files to Modify

1. `src/cognitive_hydraulics/core/verbosity.py` (new)
2. `src/cognitive_hydraulics/engine/cognitive_agent.py`
3. `src/cognitive_hydraulics/engine/rule_engine.py`
4. `src/cognitive_hydraulics/engine/actr_resolver.py`
5. `src/cognitive_hydraulics/engine/meta_monitor.py`
6. `src/cognitive_hydraulics/cli/main.py`
7. `examples/basic_example.py`
8. `examples/bug_fix_example.py`

## Testing

- Test each verbosity level (0-3) to ensure correct output
- Verify default is level 2 (thinking mode)
- Ensure backward compatibility (bool verbose still works, maps to int)
- Test that thinking output doesn't break existing functionality

### To-dos

- [ ] Create verbosity level system (VerbosityLevel enum and helpers)
- [ ] Update CognitiveAgent to use verbosity levels and add thinking output
- [ ] Update RuleEngine to show rule matching reasoning
- [ ] Update ACTRResolver to show utility calculation reasoning
- [ ] Update MetaCognitiveMonitor to show pressure calculation breakdown
- [ ] Update CLI to support verbosity levels with --verbose flag
- [ ] Update examples to use new verbosity system
- [ ] Test all verbosity levels and verify backward compatibility
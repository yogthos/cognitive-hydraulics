<!-- 9ef7207b-3260-4f78-9c4a-f89ba569a606 5896658e-f010-4912-be48-ae7ac7636579 -->
# Update Bug Fix Example with Full Execution Flow

## Overview

Transform `examples/bug_fix_example.py` to demonstrate the complete Cognitive Hydraulics decision cycle:

1. **Soar Phase**: Read file → Execute code → Detect IndexError
2. **Impasse Detection**: Multiple valid fix options create Tie impasse
3. **ACT-R Fallback**: LLM evaluates options using utility equation (U = P×G - C)
4. **Fix Application**: Apply selected fix
5. **Verification**: Re-run code to confirm fix works

## Implementation Steps

### 1. Update `examples/sort.py` with IndexError Bug

- Change `bubbleSort` to have classic IndexError: `range(0, n - i)` should be `range(0, n - i - 1)`
- Ensure bug is at line 6: `if arr[j] > arr[j + 1]:` where `j` can reach `n-1` causing `arr[j+1]` to be out of bounds
- Add a simple test case at the bottom: `if __name__ == "__main__": test_bubbleSort()`

### 2. Create Code Execution Operator (`src/cognitive_hydraulics/operators/exec_ops.py`)

- New operator: `OpRunCode(path: str)` 
- Executes Python file in subprocess
- Captures stdout, stderr, exit code
- Parses exceptions (IndexError, line numbers)
- Updates `EditorState.error_log` with exception details
- Returns `OperatorResult` with execution output/errors
- Safety: Mark as non-destructive (read-only execution)

### 3. Add Error Detection Rules (`src/cognitive_hydraulics/engine/rule_engine.py`)

- Rule: "If goal mentions 'fix bug' and error_log contains IndexError, propose running code"
- Rule: "If IndexError detected in loop context, create Tie impasse with multiple fix options"
- Pattern matching: Detect `IndexError: list index out of range` and extract line number

### 4. Enhance Impasse Detection for Tie Impasse

- Update `src/cognitive_hydraulics/engine/impasse.py` to detect Tie impasse:
- When multiple operators have same priority/utility
- When error detected but multiple valid fixes exist
- Create `TieImpasse` type that triggers ACT-R evaluation

### 5. Update ACT-R Resolver for Fix Evaluation (`src/cognitive_hydraulics/engine/actr_resolver.py`)

- Enhance `evaluate_utilities_prompt` to handle fix options:
- Input: Error type, location, code context, multiple fix options
- Output: P (probability) and C (cost) for each option
- Example: "Decrease Range: P=0.95, C=1" vs "Add Condition: P=0.90, C=2"
- Update utility calculation to select best fix

### 6. Add Fix Application Operator (`src/cognitive_hydraulics/operators/file_ops.py`)

- Enhance `OpWriteFile` or create `OpApplyFix`:
- Takes fix description from ACT-R
- Applies fix to code (e.g., change `range(0, n - i)` to `range(0, n - i - 1)`)
- Updates file content in state

### 7. Add Verification Step

- After fix applied, automatically re-run code
- Check: No exceptions + correct output
- Update goal status to "success" if verification passes

### 8. Update `examples/bug_fix_example.py`

- Set goal: "Fix the bug in sort.py so that it runs without errors and sorts the list correctly"
- Remove pre-reading of file (let Soar rules handle it)
- Enable dry-run=False to allow actual execution
- Add verbose output to show each phase:
- "Turn 1: Soar Phase - Reading sort.py"
- "Turn 1: Soar Phase - Executing sort.py"
- "Turn 1: Soar Phase - IndexError detected at line 6"
- "Turn 2: Tie Impasse - Multiple fix options"
- "Turn 2: ACT-R Fallback - Evaluating options"
- "Turn 3: Applying fix - range(0, n - i - 1)"
- "Turn 3: Verification - Code runs successfully"

### 9. Register New Operators

- Update `src/cognitive_hydraulics/operators/__init__.py` to export `OpRunCode`
- Ensure operators are discoverable by RuleEngine

## Files to Modify

- `examples/sort.py` - Update bug to IndexError
- `examples/bug_fix_example.py` - Complete rewrite for execution flow
- `src/cognitive_hydraulics/operators/exec_ops.py` - New file for execution operator
- `src/cognitive_hydraulics/operators/__init__.py` - Export new operator
- `src/cognitive_hydraulics/engine/rule_engine.py` - Add execution and error detection rules
- `src/cognitive_hydraulics/engine/impasse.py` - Add Tie impasse detection
- `src/cognitive_hydraulics/engine/actr_resolver.py` - Enhance for fix evaluation

## Testing

- Run `python examples/bug_fix_example.py` and verify:
- File is read automatically
- Code is executed
- IndexError is detected
- Tie impasse is created
- ACT-R evaluates options
- Fix is applied
- Verification passes

## Notes

- Test Harness Agent and Distance to Goal metric are deferred to future phase
- Verification is basic: re-run code + check output correctness
- Safety: Code execution is sandboxed (subprocess) but not fully isolated

### To-dos

- [x] 
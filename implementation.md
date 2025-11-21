This is a **"Cognitive Hydraulics"** implementation plan. It moves away from the standard "ReAct" loop (where an LLM does everything) and builds a structured **Neuro-Symbolic Engine** where the LLM is only used when strict logic fails.

### **I. The Tech Stack**

  * **Language:** Python 3.10+ (Typing is crucial for symbolic states).
  * **Logic Engine:** Custom Python class (Lightweight Soar mimic). Do not use the C++ Soar kernel; it is too heavy for this.
  * **Heuristic Engine (LLM):** `Ollama` (local qwen3:8b).
  * **State Management:** `Pydantic` (for strict schema validation of the State).
  * **Memory:** `ChromaDB` (for "Chunking/Learning" - storing successful past resolutions).

-----

### **II. Core Data Structures (The Ontology)**

In Soar, everything is a "State". For coding, we must rigorously define what the AI "sees".

#### **1. The State (Working Memory)**

We don't just dump text. We structure it.

```python
from pydantic import BaseModel, Field

class EditorState(BaseModel):
    open_files: dict[str, str]  # Filename -> Content
    cursor_position: dict[str, int]
    last_output: str | None = None
    error_log: list[str] = []
    git_status: str | None = None

class Goal(BaseModel):
    description: str  # e.g., "Fix the TypeError in auth.py"
    sub_goals: list['Goal'] = []
    status: str = "active" # active, success, failure
```

#### **2. The Operators (The Muscles)**

Operators are discrete actions the agent can take.

  * `Op_OpenFile(path)`
  * `Op_EditLine(file, line, content)`
  * `Op_RunTest(test_name)`
  * `Op_Grep(search_term)`

-----

### **III. The Engine Implementation**

This is the heart of the system. It is a `while` loop that strictly follows the Soar decision cycle, with the ACT-R "Hydraulic Valve" built in.

#### **Pseudo-Code Logic**

```python
class CognitiveAgent:
    def __init__(self):
        self.memory = WorkingMemory()
        self.threshold_depth = 3  # Max sub-goals before panic
        self.threshold_ambiguity = 0.8 # How confused can we be?

    def decision_cycle(self):
        while self.goal_active():
            # 1. ELABORATION (Gather Data)
            current_state = self.perceive_environment()

            # 2. PROPOSAL (Symbolic Matching)
            # Run strictly coded Python rules first. Fast & Cheap.
            possible_ops = self.rule_engine.match(current_state)

            # --- THE HYDRAULIC VALVE ---

            # Case A: Clear Winner (Logic Works)
            if len(possible_ops) == 1:
                self.apply(possible_ops[0])

            # Case B: Impasse (Tie or No Change) -> Triggers Sub-state
            elif len(possible_ops) == 0 or len(possible_ops) > 1:
                self.handle_impasse(possible_ops)

    def handle_impasse(self, options):
        # CHECK: Are we too deep? (Pressure too high?)
        if self.stack_depth > self.threshold_depth:
            print("⚠️ LOGIC FAILURE. ENGAGING ACT-R FALLBACK.")
            self.act_r_resolve(options)  # Switch to LLM Intuition
        else:
            print("Creating Sub-State to resolve logic...")
            self.create_subgoal() # Classic Soar recursion

    def act_r_resolve(self, options):
        # This uses the LLM to calculate "Activation Energy"
        # Prompt: "Given Goal G and State S, assign a probability of success (P)
        # and cost (C) to these operators: [Op1, Op2...]"

        utilities = self.llm.get_utilities(self.goal, options)
        # ACT-R Equation: U = P*G - C
        best_op = max(utilities, key=lambda x: x.utility)

        self.apply(best_op)
        # CRITICAL: Learn from this. If it works, save as a Rule (Chunking).
        self.learn_chunk(best_op)
```

-----

### **IV. Phase-by-Phase Implementation Plan**

#### **Phase 1: The Symbolic Skeleton**

  * **Goal:** Build the `CognitiveAgent` class that can solve a problem *without* an LLM if the rules are perfect.
  * **Action:**
      * Define `State` Pydantic models.
      * Write 5 hard-coded rules (e.g., `IF last_output == "FileNotFound" THEN Op_SearchFile(filename)`).
      * Test the agent on a dummy file system. It should succeed deterministically.

#### **Phase 2: The "Intuition" Integration**

  * **Goal:** Connect the LLM to handle the "Tie Impasse" (Conflict Resolution).
  * **Action:**
      * Implement the `act_r_resolve` function.
      * **Prompt Engineering:** Create a prompt that enforces the ACT-R math.
          * *Bad Prompt:* "Which one is best?"
          * *Good Prompt:* "For each operator, estimate probability of success (0.0-1.0) and execution cost (1-10). Return JSON."
      * Connect to a local fast model (e.g., Llama 3 8B via Ollama) to keep the "reflex" loop fast.

#### **Phase 3: Tooling & The "Hands"**

  * **Goal:** Give the agent actual power.
  * **Action:**
      * Implement a **Sandboxed File System** (Docker container or temp dir).
      * Map `Op_Edit` to actual Python file I/O.
      * Map `Op_Run` to `subprocess.run()`.
      * *Safety:* Add a "Human Check" middleware if the `Utility` score is below a certain safety margin.

#### **Phase 4: Chunking (The Memory Layer)**

  * **Goal:** Make the agent smarter over time.
  * **Action:**
      * When `act_r_resolve` leads to a `Goal Success` state, save the (State, Operator) pair to ChromaDB.
      * **Update the Proposal Phase:** Before running Python rules, query ChromaDB: *"Have I seen this exact situation before?"*
      * If yes, bypass the LLM and execute the remembered action instantly. This mimics human skill acquisition (moving from declarative to procedural memory).

-----

### **V. Example Scenario: Debugging a Loop**

1.  **State:** Error log shows `IndexError: list index out of range`.
2.  **Soar Layer:** Rule matches: `IF error == IndexError THEN Suggest Op_CheckLoopBounds`.
3.  **Impasse:** There are *two* loops in the file. Logic doesn't know which one to check.
      * *Options:* `CheckLoopA`, `CheckLoopB`.
4.  **Threshold:** Depth is low, so it creates a **Sub-state**.
5.  **Sub-state Logic:** Tries to reason. "Is loop A related to the variable in the error?"
6.  **Impasse 2:** It can't determine that statically. Pressure rises.
7.  **Fallback Triggered:** Switches to **ACT-R Mode**.
8.  **LLM Query:** "Look at the code. Which loop is more likely to fail given `IndexError`?"
      * LLM Intuition: "Loop B iterates `i+1`, highly likely to overflow." -\> High $P$ value.
9.  **Action:** Agent edits Loop B.
10. **Result:** Tests pass.
11. **Chunking:** System records: *"When seeing `i+1` and `IndexError`, go straight to that loop."*

### **Next Step**

This architecture requires a robust way for the Python code to "see" the code files as structural objects (AST) rather than just strings.

[Avoid Messy Code: Design Patterns for AI Agents in Python](https://www.youtube.com/watch?v=8_liatgLkLc)

This video explains design patterns like **Chain of Responsibility** and **Strategy**, which are essential for implementing the "Rules -\> Impasse -\> Fallback" logic cleanly in Python without creating a spaghetti code mess.



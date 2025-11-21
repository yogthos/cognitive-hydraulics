# Cognitive Hydraulics Implementation Roadmap

## Core Architectural Decisions

### 1. Code Understanding: Tree-sitter
- **Decision**: Use tree-sitter for multi-language AST parsing
- **Rationale**: Supports Python, JavaScript, Rust, Go, Java, etc. without separate parsers
- **Implementation**: Operators will work with structured tree-sitter nodes, not raw strings

### 2. LLM Reliability: JSON Schema Enforcement
- **Decision**: All LLM responses must conform to strict JSON schemas
- **Rationale**: Prevents hallucination, ensures parseable output
- **Implementation**: Use function calling/structured output mode in Ollama

### 3. State Management: Context Window Management
- **Decision**: Intelligent state summarization to fit context limits
- **Rationale**: Full file contents won't fit; need smart compression
- **Implementation**:
  - Store full state in working memory
  - Provide compressed view to LLM (relevant excerpts only)
  - Use tree-sitter to extract only relevant code blocks

### 4. Safety: Human-in-the-Loop for Destructive Actions
- **Decision**: Require approval for any write/delete operations
- **Rationale**: Prevent accidental damage to user's system
- **Action Classification**:
  - ✅ **Safe (Auto-execute)**: Read file, grep, list directory, check syntax
  - ⚠️ **Destructive (Require Approval)**: Write file, delete file, run commands, git operations

---

## Phase-by-Phase Implementation Plan

### **Phase 0: Project Bootstrap** (Days 1-2)

**Goal**: Set up the foundation with proper tooling and structure.

#### Directory Structure
```
cognitive-hydraulics/
├── src/
│   └── cognitive_hydraulics/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── state.py          # Pydantic State models
│       │   ├── goal.py           # Goal hierarchy
│       │   ├── working_memory.py # State history tracker
│       │   └── operator.py       # Base Operator class
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── cognitive_agent.py    # Main decision cycle
│       │   ├── rule_engine.py        # Soar symbolic layer
│       │   ├── actr_resolver.py      # ACT-R utility calculator
│       │   └── meta_monitor.py       # Threshold watcher
│       ├── operators/
│       │   ├── __init__.py
│       │   ├── file_ops.py       # Read/Write/Edit operations
│       │   ├── search_ops.py     # Grep/Find operations
│       │   ├── execution_ops.py  # Run commands/tests
│       │   └── analysis_ops.py   # Tree-sitter based analysis
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py         # Ollama integration
│       │   ├── prompts.py        # Prompt templates
│       │   └── schemas.py        # JSON schemas for responses
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── chunk_store.py    # ChromaDB wrapper
│       │   └── learning.py       # Chunking logic
│       └── utils/
│           ├── __init__.py
│           ├── tree_sitter_utils.py  # AST parsing helpers
│           └── context_manager.py    # Context window compression
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── examples/
├── requirements.txt
├── pyproject.toml
└── README.md
```

#### Dependencies (requirements.txt)
```txt
# Core
pydantic>=2.5.0
python-dotenv>=1.0.0

# LLM
ollama>=0.1.0

# Memory
chromadb>=0.4.0

# Code Analysis
tree-sitter>=0.20.0
tree-sitter-python>=0.20.0
tree-sitter-javascript>=0.20.0
tree-sitter-typescript>=0.20.0
tree-sitter-rust>=0.20.0
tree-sitter-go>=0.20.0

# Utilities
rich>=13.0.0  # Beautiful terminal output
typer>=0.9.0  # CLI interface

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

#### Tasks
- [x] Create directory structure
- [ ] Initialize Python package with pyproject.toml
- [ ] Install all dependencies
- [ ] Set up pytest configuration
- [ ] Create basic README

---

### **Phase 1: Core Data Models** (Days 3-5)

**Goal**: Define the ontology - State, Goal, Operator with Pydantic.

#### 1.1 State Definition (`src/cognitive_hydraulics/core/state.py`)

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime

class FileContent(BaseModel):
    """Represents a file with parsed structure."""
    path: str
    content: str
    language: str
    tree_sitter_tree: Optional[dict] = None  # Serialized AST
    last_modified: datetime

class EditorState(BaseModel):
    """Current state of the development environment."""
    open_files: Dict[str, FileContent] = Field(default_factory=dict)
    cursor_position: Dict[str, int] = Field(default_factory=dict)
    last_output: Optional[str] = None
    error_log: List[str] = Field(default_factory=list)
    git_status: Optional[str] = None
    working_directory: str

    def compress_for_llm(self) -> dict:
        """Return a context-window-friendly version."""
        # Only include relevant excerpts, not full files
        pass

class Goal(BaseModel):
    """Represents a goal or sub-goal."""
    description: str
    parent_goal: Optional['Goal'] = None
    sub_goals: List['Goal'] = Field(default_factory=list)
    status: str = "active"  # active, success, failure
    priority: float = 1.0

    def depth(self) -> int:
        """Calculate nesting depth."""
        if self.parent_goal is None:
            return 0
        return 1 + self.parent_goal.depth()
```

#### 1.2 Operator Base Class (`src/cognitive_hydraulics/core/operator.py`)

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional

class OperatorResult(BaseModel):
    """Result of executing an operator."""
    success: bool
    new_state: Optional['EditorState'] = None
    output: str
    error: Optional[str] = None

class Operator(ABC):
    """Base class for all operators."""

    def __init__(self, name: str, is_destructive: bool = False):
        self.name = name
        self.is_destructive = is_destructive

    @abstractmethod
    def is_applicable(self, state: 'EditorState', goal: 'Goal') -> bool:
        """Can this operator be applied in the current state?"""
        pass

    @abstractmethod
    async def execute(self, state: 'EditorState') -> OperatorResult:
        """Execute the operator."""
        pass

    def requires_approval(self) -> bool:
        """Should this require human approval?"""
        return self.is_destructive
```

#### Tasks
- [ ] Implement State models with full typing
- [ ] Implement Goal hierarchy with depth tracking
- [ ] Create Operator base class
- [ ] Add context compression logic to EditorState
- [ ] Write unit tests for all models

---

### **Phase 2: Tree-sitter Integration** (Days 6-8)

**Goal**: Build the code understanding layer.

#### 2.1 Tree-sitter Utilities (`src/cognitive_hydraulics/utils/tree_sitter_utils.py`)

```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
# ... other languages

class CodeAnalyzer:
    """Multi-language code analyzer using tree-sitter."""

    def __init__(self):
        self.parsers = {
            'python': self._init_parser(tspython.language()),
            'javascript': self._init_parser(tsjavascript.language()),
            # Add more languages
        }

    def parse_file(self, content: str, language: str) -> dict:
        """Parse code into AST."""
        parser = self.parsers.get(language)
        if not parser:
            raise ValueError(f"Unsupported language: {language}")

        tree = parser.parse(bytes(content, "utf8"))
        return self._serialize_tree(tree)

    def extract_function(self, tree: dict, function_name: str) -> str:
        """Extract a specific function from AST."""
        pass

    def find_error_location(self, tree: dict, error_line: int) -> dict:
        """Find the syntactic context of an error."""
        pass

    def get_imports(self, tree: dict) -> List[str]:
        """Extract all import statements."""
        pass
```

#### 2.2 Context Manager (`src/cognitive_hydraulics/utils/context_manager.py`)

```python
class ContextWindowManager:
    """Manages LLM context to fit within token limits."""

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens
        self.code_analyzer = CodeAnalyzer()

    def compress_state(self, state: EditorState, goal: Goal) -> dict:
        """
        Intelligently compress state for LLM.

        Strategy:
        1. Include goal description (always)
        2. Include last error (if exists)
        3. Include relevant code excerpts only:
           - If error references line N, include lines N-10 to N+10
           - If goal mentions a function, extract that function only
        4. Include git status summary (not full diff)
        """
        compressed = {
            "goal": goal.description,
            "error": state.error_log[-1] if state.error_log else None,
            "relevant_code": {},
            "git_summary": self._summarize_git(state.git_status)
        }

        # Use tree-sitter to extract only relevant sections
        for file_path, file_content in state.open_files.items():
            if self._is_relevant_to_goal(file_path, goal):
                relevant_section = self._extract_relevant_section(
                    file_content, goal
                )
                compressed["relevant_code"][file_path] = relevant_section

        return compressed

    def _extract_relevant_section(self, file: FileContent, goal: Goal) -> str:
        """Use tree-sitter to extract only the relevant function/class."""
        # Parse the tree, find the node matching the goal, return that snippet
        pass
```

#### Tasks
- [ ] Set up tree-sitter parsers for Python, JS, TS, Rust, Go
- [ ] Implement AST parsing and serialization
- [ ] Add function/class extraction utilities
- [ ] Build context compression logic
- [ ] Write tests with sample code files

---

### **Phase 3: Soar Decision Engine** (Days 9-14)

**Goal**: Implement the symbolic reasoning layer.

#### 3.1 Rule Engine (`src/cognitive_hydraulics/engine/rule_engine.py`)

```python
from typing import List, Callable
from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator

class Rule:
    """A symbolic production rule."""

    def __init__(
        self,
        name: str,
        condition: Callable[[EditorState, Goal], bool],
        operator_factory: Callable[[EditorState, Goal], Operator],
        priority: float = 1.0
    ):
        self.name = name
        self.condition = condition
        self.operator_factory = operator_factory
        self.priority = priority

    def matches(self, state: EditorState, goal: Goal) -> bool:
        """Does this rule match the current state?"""
        return self.condition(state, goal)

class RuleEngine:
    """Symbolic pattern matcher (Soar-like)."""

    def __init__(self):
        self.rules: List[Rule] = []
        self._register_default_rules()

    def propose_operators(
        self,
        state: EditorState,
        goal: Goal
    ) -> List[Operator]:
        """
        Match all rules against current state.
        Returns list of applicable operators.
        """
        proposals = []
        for rule in self.rules:
            if rule.matches(state, goal):
                operator = rule.operator_factory(state, goal)
                proposals.append((operator, rule.priority))

        # Sort by priority
        proposals.sort(key=lambda x: x[1], reverse=True)
        return [op for op, _ in proposals]

    def _register_default_rules(self):
        """Register hardcoded production rules."""

        # Rule: If file mentioned in goal but not open, open it
        self.rules.append(Rule(
            name="open_mentioned_file",
            condition=lambda s, g: self._file_mentioned_but_not_open(s, g),
            operator_factory=lambda s, g: OpOpenFile(
                self._extract_filename(g.description)
            ),
            priority=2.0
        ))

        # Rule: If error log shows FileNotFound, search for file
        self.rules.append(Rule(
            name="search_missing_file",
            condition=lambda s, g: "FileNotFoundError" in str(s.error_log),
            operator_factory=lambda s, g: OpSearchFile(
                self._extract_filename_from_error(s.error_log[-1])
            ),
            priority=3.0
        ))

        # Add more rules...
```

#### 3.2 Meta-Cognitive Monitor (`src/cognitive_hydraulics/engine/meta_monitor.py`)

```python
import time
from dataclasses import dataclass

@dataclass
class CognitiveMetrics:
    """Tracks cognitive load."""
    goal_depth: int
    time_in_state_ms: float
    impasse_count: int
    operator_ambiguity: float  # 0.0 = clear, 1.0 = total confusion

class MetaCognitiveMonitor:
    """Watches for cognitive overload."""

    def __init__(
        self,
        depth_threshold: int = 3,
        time_threshold_ms: float = 500
    ):
        self.depth_threshold = depth_threshold
        self.time_threshold_ms = time_threshold_ms
        self.state_entry_time = time.time()

    def reset_timer(self):
        """Call when state changes."""
        self.state_entry_time = time.time()

    def calculate_pressure(self, metrics: CognitiveMetrics) -> float:
        """
        Calculate cognitive pressure (0.0 = calm, 1.0 = panic).

        Pressure increases with:
        - Goal depth
        - Time stuck in state
        - Number of equally-viable operators (ambiguity)
        """
        depth_pressure = min(metrics.goal_depth / self.depth_threshold, 1.0)
        time_pressure = min(metrics.time_in_state_ms / self.time_threshold_ms, 1.0)
        ambiguity_pressure = metrics.operator_ambiguity

        # Weighted combination
        return (
            0.4 * depth_pressure +
            0.3 * time_pressure +
            0.3 * ambiguity_pressure
        )

    def should_trigger_fallback(self, metrics: CognitiveMetrics) -> bool:
        """Should we abandon symbolic reasoning?"""
        return self.calculate_pressure(metrics) > 0.7
```

#### 3.3 Cognitive Agent (Soar Cycle) (`src/cognitive_hydraulics/engine/cognitive_agent.py`)

```python
class ImpasseType(Enum):
    NO_CHANGE = "no_change"  # No operators proposed
    TIE = "tie"              # Multiple equal-priority operators

class CognitiveAgent:
    """The main reasoning engine."""

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.meta_monitor = MetaCognitiveMonitor()
        self.current_goal: Optional[Goal] = None
        self.current_state: Optional[EditorState] = None
        self.goal_stack: List[Goal] = []

    async def solve(self, goal: Goal, initial_state: EditorState):
        """Main decision cycle."""
        self.current_goal = goal
        self.current_state = initial_state

        while not self._goal_achieved():
            # === SOAR DECISION CYCLE ===

            # 1. ELABORATION: Perceive environment
            self.current_state = self._perceive()

            # 2. PROPOSAL: Run rule matching
            proposed_ops = self.rule_engine.propose_operators(
                self.current_state,
                self.current_goal
            )

            # 3. DECISION: Select operator
            if len(proposed_ops) == 1:
                # Clear winner - execute immediately
                await self._apply_operator(proposed_ops[0])
                self.meta_monitor.reset_timer()

            elif len(proposed_ops) == 0:
                # NO CHANGE IMPASSE
                await self._handle_impasse(ImpasseType.NO_CHANGE, [])

            else:
                # TIE IMPASSE (multiple operators)
                await self._handle_impasse(ImpasseType.TIE, proposed_ops)

    async def _handle_impasse(
        self,
        impasse_type: ImpasseType,
        operators: List[Operator]
    ):
        """The hydraulic valve decision point."""

        metrics = self._calculate_metrics()

        if self.meta_monitor.should_trigger_fallback(metrics):
            print("⚠️  COGNITIVE OVERLOAD - SWITCHING TO ACT-R FALLBACK")
            await self._actr_fallback(operators)
        else:
            print("💭 Creating sub-goal to resolve impasse...")
            self._create_subgoal(impasse_type, operators)

    def _calculate_metrics(self) -> CognitiveMetrics:
        """Calculate current cognitive load."""
        time_in_state = (time.time() - self.meta_monitor.state_entry_time) * 1000
        return CognitiveMetrics(
            goal_depth=self.current_goal.depth(),
            time_in_state_ms=time_in_state,
            impasse_count=len(self.goal_stack),
            operator_ambiguity=0.5  # Will be calculated based on operator similarity
        )
```

#### Tasks
- [ ] Implement Rule class and RuleEngine
- [ ] Add 10+ hardcoded rules for common scenarios
- [ ] Implement MetaCognitiveMonitor with pressure calculation
- [ ] Build CognitiveAgent with Soar decision cycle
- [ ] Add impasse detection and sub-goal creation
- [ ] Write integration tests

---

### **Phase 4: LLM Integration with JSON Schemas** (Days 15-19)

**Goal**: Connect Ollama with strict structured output.

#### 4.1 JSON Schemas (`src/cognitive_hydraulics/llm/schemas.py`)

```python
from pydantic import BaseModel, Field
from typing import List

class OperatorSuggestion(BaseModel):
    """Schema for LLM-generated operator proposals."""
    name: str = Field(description="Name of the operator (e.g., 'edit_file')")
    reasoning: str = Field(description="Why this operator might work")
    parameters: dict = Field(description="Parameters for the operator")

class OperatorProposal(BaseModel):
    """Response schema for No-Change impasse."""
    operators: List[OperatorSuggestion] = Field(
        min_length=1,
        max_length=5,
        description="Suggested operators to try"
    )

class UtilityEstimate(BaseModel):
    """Schema for ACT-R utility calculation."""
    operator_name: str
    probability_of_success: float = Field(ge=0.0, le=1.0)
    estimated_cost: float = Field(ge=1.0, le=10.0)
    reasoning: str

class UtilityEvaluation(BaseModel):
    """Response schema for Tie impasse."""
    evaluations: List[UtilityEstimate]
```

#### 4.2 LLM Client (`src/cognitive_hydraulics/llm/client.py`)

```python
import ollama
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient:
    """Ollama client with JSON schema enforcement."""

    def __init__(self, model: str = "qwen2.5:8b"):
        self.model = model
        self.client = ollama.Client()

    async def structured_query(
        self,
        prompt: str,
        response_schema: Type[T],
        system_prompt: str = ""
    ) -> T:
        """
        Query LLM with enforced JSON schema.

        Uses Ollama's function calling / structured output mode.
        """
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            format=response_schema.model_json_schema(),  # Enforce schema
            options={"temperature": 0.3}  # Lower temp for more deterministic
        )

        # Parse and validate response
        json_response = response['message']['content']
        return response_schema.model_validate_json(json_response)
```

#### 4.3 Prompt Templates (`src/cognitive_hydraulics/llm/prompts.py`)

```python
class PromptTemplates:
    """Structured prompts for different impasse types."""

    SYSTEM_PROMPT = """You are a reasoning assistant in a cognitive architecture.
You must respond with ONLY valid JSON matching the provided schema.
Be concise and precise. Focus on actionable operators."""

    @staticmethod
    def generate_operators_prompt(state_summary: dict, goal: str) -> str:
        """For No-Change impasse: Generate new operators."""
        return f"""
GOAL: {goal}

CURRENT STATE:
- Error: {state_summary.get('error', 'None')}
- Open files: {list(state_summary.get('relevant_code', {}).keys())}

The symbolic reasoning system has no applicable rules for this situation.
Suggest 2-3 operators that could make progress toward the goal.

Each operator should be a concrete action like:
- read_file(path)
- search_codebase(term)
- edit_function(file, function_name, new_body)
"""

    @staticmethod
    def evaluate_utilities_prompt(
        state_summary: dict,
        goal: str,
        operators: List[str]
    ) -> str:
        """For Tie impasse: Rate P and C for each operator."""
        return f"""
GOAL: {goal}

CURRENT STATE:
{state_summary}

CANDIDATE OPERATORS:
{chr(10).join(f"- {op}" for op in operators)}

For each operator, estimate:
1. Probability of Success (0.0 to 1.0): How likely will this solve/advance the goal?
2. Estimated Cost (1 to 10): How expensive is this action? (1=quick, 10=very slow)

Provide your reasoning for each estimate.
"""
```

#### 4.4 ACT-R Resolver (`src/cognitive_hydraulics/engine/actr_resolver.py`)

```python
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import UtilityEvaluation
import random

class ACTRResolver:
    """ACT-R style conflict resolution using LLM."""

    def __init__(self, goal_value: float = 10.0, noise_stddev: float = 0.5):
        self.llm = LLMClient()
        self.G = goal_value  # Value of achieving the goal
        self.noise_stddev = noise_stddev

    async def resolve(
        self,
        operators: List[Operator],
        state: EditorState,
        goal: Goal
    ) -> Operator:
        """
        Use LLM to estimate utilities, then select best.

        ACT-R Utility: U = P * G - C + Noise
        """
        # Compress state for LLM
        state_summary = state.compress_for_llm()

        # Query LLM for P and C estimates
        prompt = PromptTemplates.evaluate_utilities_prompt(
            state_summary,
            goal.description,
            [op.name for op in operators]
        )

        evaluation: UtilityEvaluation = await self.llm.structured_query(
            prompt=prompt,
            response_schema=UtilityEvaluation,
            system_prompt=PromptTemplates.SYSTEM_PROMPT
        )

        # Calculate utilities
        utilities = []
        for op, est in zip(operators, evaluation.evaluations):
            P = est.probability_of_success
            C = est.estimated_cost
            noise = random.gauss(0, self.noise_stddev)

            U = P * self.G - C + noise

            utilities.append((op, U, est.reasoning))
            print(f"  {op.name}: U={U:.2f} (P={P:.2f}, C={C:.1f}) - {est.reasoning}")

        # Select highest utility
        best_op, best_U, reasoning = max(utilities, key=lambda x: x[1])
        print(f"✓ Selected {best_op.name} with utility {best_U:.2f}")

        return best_op
```

#### Tasks
- [ ] Define JSON schemas for all LLM responses
- [ ] Implement LLMClient with schema enforcement
- [ ] Write prompt templates for both impasse types
- [ ] Implement ACTRResolver with utility calculation
- [ ] Test with real Ollama instance
- [ ] Handle LLM failures gracefully (timeout, invalid JSON)

---

### **Phase 5: Operators with Safety** (Days 20-24)

**Goal**: Implement real operators with human approval for destructive actions.

#### 5.1 File Operators (`src/cognitive_hydraulics/operators/file_ops.py`)

```python
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.state import EditorState, FileContent
import os

class OpReadFile(Operator):
    """Safe: Read file contents."""

    def __init__(self, path: str):
        super().__init__(name=f"read_file({path})", is_destructive=False)
        self.path = path

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        return os.path.exists(self.path)

    async def execute(self, state: EditorState) -> OperatorResult:
        try:
            with open(self.path, 'r') as f:
                content = f.read()

            # Parse with tree-sitter
            analyzer = CodeAnalyzer()
            language = self._detect_language(self.path)
            tree = analyzer.parse_file(content, language)

            # Update state
            new_state = state.model_copy(deep=True)
            new_state.open_files[self.path] = FileContent(
                path=self.path,
                content=content,
                language=language,
                tree_sitter_tree=tree,
                last_modified=datetime.now()
            )

            return OperatorResult(
                success=True,
                new_state=new_state,
                output=f"Opened {self.path}"
            )
        except Exception as e:
            return OperatorResult(
                success=False,
                output="",
                error=str(e)
            )

class OpWriteFile(Operator):
    """Destructive: Write file (requires approval)."""

    def __init__(self, path: str, content: str):
        super().__init__(name=f"write_file({path})", is_destructive=True)
        self.path = path
        self.content = content

    def is_applicable(self, state: EditorState, goal: Goal) -> bool:
        return True  # Can always attempt to write

    async def execute(self, state: EditorState) -> OperatorResult:
        # This will be wrapped by approval middleware
        try:
            with open(self.path, 'w') as f:
                f.write(self.content)

            return OperatorResult(
                success=True,
                new_state=state,  # State update happens after approval
                output=f"Wrote {len(self.content)} bytes to {self.path}"
            )
        except Exception as e:
            return OperatorResult(
                success=False,
                output="",
                error=str(e)
            )
```

#### 5.2 Approval System (`src/cognitive_hydraulics/core/approval.py`)

```python
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

class ApprovalSystem:
    """Human-in-the-loop for destructive actions."""

    @staticmethod
    async def request_approval(operator: Operator, state: EditorState) -> bool:
        """
        Display operator details and ask for approval.
        Returns True if approved, False otherwise.
        """
        console.print()
        console.print(Panel(
            f"[bold yellow]⚠️  DESTRUCTIVE ACTION REQUIRES APPROVAL[/bold yellow]\n\n"
            f"Operator: [cyan]{operator.name}[/cyan]\n"
            f"Type: [red]{'WRITE' if 'write' in operator.name else 'DELETE'}[/red]",
            title="Human Approval Required"
        ))

        # Show what will change
        if isinstance(operator, OpWriteFile):
            console.print("\n[bold]New content:[/bold]")
            syntax = Syntax(
                operator.content[:500],  # Preview first 500 chars
                operator._detect_language(operator.path),
                line_numbers=True
            )
            console.print(syntax)

        # Ask for approval
        response = console.input("\n[bold]Approve? (y/n/e=edit): [/bold]").lower()

        if response == 'e':
            # Allow user to edit the operator parameters
            # (Future: open in $EDITOR)
            return False

        return response == 'y'

    @staticmethod
    async def wrap_operator(operator: Operator, state: EditorState) -> OperatorResult:
        """
        Wrap operator execution with approval check.
        """
        if operator.requires_approval():
            approved = await ApprovalSystem.request_approval(operator, state)
            if not approved:
                return OperatorResult(
                    success=False,
                    output="",
                    error="User denied approval"
                )

        # Execute if approved or if safe
        return await operator.execute(state)
```

#### Update CognitiveAgent to use approval:

```python
# In cognitive_agent.py
async def _apply_operator(self, operator: Operator):
    """Execute operator with approval if needed."""
    result = await ApprovalSystem.wrap_operator(operator, self.current_state)

    if result.success:
        self.current_state = result.new_state
        print(f"✓ {result.output}")
    else:
        print(f"✗ {result.error}")
        # Add failure to error log
        self.current_state.error_log.append(result.error)
```

#### Tasks
- [ ] Implement read-only operators (Read, Grep, List)
- [ ] Implement destructive operators (Write, Delete, Execute)
- [ ] Build ApprovalSystem with rich UI
- [ ] Integrate approval into CognitiveAgent
- [ ] Add operator rollback capability
- [ ] Test approval flow

---

### **Phase 6: Memory & Learning** (Days 25-28)

**Goal**: Implement chunking - learning from successful ACT-R resolutions.

#### 6.1 Chunk Store (`src/cognitive_hydraulics/memory/chunk_store.py`)

```python
import chromadb
from chromadb.config import Settings

class ChunkStore:
    """Persistent memory of successful operator selections."""

    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        self.collection = self.client.get_or_create_collection(
            name="successful_resolutions",
            metadata={"description": "Learned operator chunks"}
        )

    def store_chunk(
        self,
        state_signature: str,
        operator_name: str,
        goal_description: str,
        success_outcome: str
    ):
        """
        Store a successful resolution for future retrieval.

        state_signature: Compressed representation of the state
        operator_name: The operator that worked
        """
        self.collection.add(
            documents=[state_signature],
            metadatas=[{
                "operator": operator_name,
                "goal": goal_description,
                "outcome": success_outcome
            }],
            ids=[f"{hash(state_signature)}_{operator_name}"]
        )

    def recall_similar(self, state_signature: str, n_results: int = 3):
        """Query for similar past situations."""
        results = self.collection.query(
            query_texts=[state_signature],
            n_results=n_results
        )
        return results
```

#### 6.2 Learning System (`src/cognitive_hydraulics/memory/learning.py`)

```python
class LearningSystem:
    """Converts successful ACT-R guesses into fast rules."""

    def __init__(self, chunk_store: ChunkStore, rule_engine: RuleEngine):
        self.chunk_store = chunk_store
        self.rule_engine = rule_engine

    def observe_success(
        self,
        initial_state: EditorState,
        operator: Operator,
        goal: Goal,
        final_state: EditorState
    ):
        """
        Called when an ACT-R resolution leads to success.
        Creates a new rule to short-circuit future reasoning.
        """
        # Create state signature (compressed representation)
        state_sig = self._create_signature(initial_state, goal)

        # Store in ChromaDB
        self.chunk_store.store_chunk(
            state_signature=state_sig,
            operator_name=operator.name,
            goal_description=goal.description,
            success_outcome="Goal achieved"
        )

        # Convert to a new production rule
        new_rule = self._chunk_to_rule(state_sig, operator)
        self.rule_engine.rules.append(new_rule)

        print(f"📚 LEARNED: {state_sig} -> {operator.name}")

    def _create_signature(self, state: EditorState, goal: Goal) -> str:
        """
        Create a "fingerprint" of the state.
        Should capture the essential features that led to success.
        """
        signature_parts = [
            f"goal:{goal.description[:50]}",
            f"error:{state.error_log[-1] if state.error_log else 'none'}",
            f"files:{sorted(state.open_files.keys())}"
        ]
        return " | ".join(signature_parts)

    def _chunk_to_rule(self, signature: str, operator: Operator) -> Rule:
        """Convert a learned chunk into a production rule."""
        def condition(state: EditorState, goal: Goal) -> bool:
            current_sig = self._create_signature(state, goal)
            # Simple string matching (could use fuzzy matching)
            return signature == current_sig

        def operator_factory(state: EditorState, goal: Goal) -> Operator:
            # Recreate the operator (needs better serialization)
            return operator

        return Rule(
            name=f"learned_{hash(signature)}",
            condition=condition,
            operator_factory=operator_factory,
            priority=5.0  # Learned rules have high priority!
        )
```

#### Update CognitiveAgent to trigger learning:

```python
# In cognitive_agent.py
async def _actr_fallback(self, operators: List[Operator]):
    """ACT-R resolution with learning."""
    # Use ACT-R to select operator
    resolver = ACTRResolver()
    selected_op = await resolver.resolve(operators, self.current_state, self.current_goal)

    # Store initial state
    state_before = self.current_state.model_copy(deep=True)

    # Execute
    await self._apply_operator(selected_op)

    # If this led to goal success, learn from it
    if self._goal_achieved():
        self.learning_system.observe_success(
            initial_state=state_before,
            operator=selected_op,
            goal=self.current_goal,
            final_state=self.current_state
        )
```

#### Tasks
- [ ] Set up ChromaDB with proper schema
- [ ] Implement ChunkStore for vector search
- [ ] Build LearningSystem to convert chunks to rules
- [ ] Integrate learning into CognitiveAgent
- [ ] Add rule priority management
- [ ] Test learning over multiple episodes

---

### **Phase 7: CLI & Integration** (Days 29-32)

**Goal**: Build a usable CLI interface and end-to-end testing.

#### 7.1 CLI Interface (`src/cognitive_hydraulics/cli.py`)

```python
import typer
from rich.console import Console
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent
from cognitive_hydraulics.core.state import EditorState, Goal

app = typer.Typer()
console = Console()

@app.command()
def solve(
    goal: str = typer.Argument(..., help="What should the agent do?"),
    workspace: str = typer.Option(".", help="Working directory"),
    depth_threshold: int = typer.Option(3, help="Max sub-goal depth"),
    model: str = typer.Option("qwen2.5:8b", help="Ollama model to use")
):
    """Run the Cognitive Hydraulics agent."""

    console.print(f"[bold]🧠 Cognitive Hydraulics Engine[/bold]\n")
    console.print(f"Goal: {goal}")
    console.print(f"Workspace: {workspace}\n")

    # Initialize agent
    agent = CognitiveAgent()

    # Create initial state
    initial_state = EditorState(working_directory=workspace)

    # Create goal
    goal_obj = Goal(description=goal)

    # Solve
    import asyncio
    asyncio.run(agent.solve(goal_obj, initial_state))

if __name__ == "__main__":
    app()
```

#### 7.2 Example Scenarios

**Scenario 1: Fix a Bug**
```bash
cognitive-hydraulics solve "Fix the IndexError in process_data() function"
```

**Scenario 2: Add a Feature**
```bash
cognitive-hydraulics solve "Add input validation to the user registration form"
```

#### Tasks
- [ ] Build CLI with Typer
- [ ] Add configuration file support
- [ ] Create example scenarios
- [ ] Write end-to-end tests
- [ ] Add logging and trace output
- [ ] Performance profiling

---

### **Phase 8: Documentation & Polish** (Days 33-35)

#### Tasks
- [ ] Write comprehensive README
- [ ] API documentation
- [ ] Architecture diagram
- [ ] Tutorial notebook
- [ ] Performance benchmarks
- [ ] Comparison with pure LLM approach

---

## Success Metrics

1. **Correctness**: Can solve at least 5 realistic coding tasks
2. **Explainability**: Full trace of Soar -> ACT-R transitions
3. **Learning**: Measurable speedup on repeated similar tasks
4. **Safety**: Zero destructive actions without approval
5. **Efficiency**: ACT-R fallback triggered < 30% of the time (most things should be rule-based)

---

## Next Immediate Actions

1. Set up project structure (Phase 0)
2. Install dependencies
3. Implement core State models (Phase 1)
4. Set up tree-sitter for Python (Phase 2, minimal)
5. Build basic RuleEngine with 3 hardcoded rules (Phase 3, minimal)

Would you like to start implementing now?


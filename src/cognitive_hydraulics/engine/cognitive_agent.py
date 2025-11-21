"""Main cognitive agent implementing the Soar decision cycle."""

from __future__ import annotations

from typing import Optional
import asyncio

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.working_memory import WorkingMemory
from cognitive_hydraulics.core.verbosity import should_print, normalize_verbose, format_thinking, VerbosityLevel
from cognitive_hydraulics.engine.rule_engine import RuleEngine
from cognitive_hydraulics.engine.meta_monitor import MetaCognitiveMonitor, CognitiveMetrics
from cognitive_hydraulics.engine.impasse import ImpasseDetector, Impasse, ImpasseType
from cognitive_hydraulics.engine.actr_resolver import ACTRResolver
from cognitive_hydraulics.engine.evaluator import CodeEvaluator
from cognitive_hydraulics.engine.evolution import EvolutionarySolver
from cognitive_hydraulics.safety.middleware import SafetyMiddleware, SafetyConfig
from cognitive_hydraulics.memory.unified_memory import UnifiedMemory
from cognitive_hydraulics.memory.chunk import create_chunk_from_success
from cognitive_hydraulics.llm.client import LLMClient
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from cognitive_hydraulics.config.settings import Config


class CognitiveAgent:
    """
    Main reasoning agent implementing Cognitive Hydraulics architecture.

    Combines:
    - Soar-style symbolic reasoning (System 2)
    - Impasse detection and sub-goaling
    - Meta-cognitive monitoring (pressure valve)
    - (Future: ACT-R fallback in Phase 4)
    """

    def __init__(
        self,
        depth_threshold: Optional[int] = None,
        time_threshold_ms: Optional[float] = None,
        max_cycles: Optional[int] = None,
        safety_config: Optional[SafetyConfig] = None,
        enable_learning: bool = True,
        chunk_store_path: Optional[str] = None,
        config: Optional["Config"] = None,
    ):
        """
        Initialize the cognitive agent.

        Args:
            depth_threshold: Max sub-goal depth before fallback (overrides config if provided)
            time_threshold_ms: Max time in state before fallback (overrides config if provided)
            max_cycles: Maximum decision cycles (overrides config if provided)
            safety_config: Safety configuration (uses defaults if None)
            enable_learning: Enable chunking/learning from experience
            chunk_store_path: Path for persistent chunk storage (None = in-memory)
            config: Configuration object (if None, uses defaults)
        """
        if config:
            depth = (
                depth_threshold
                if depth_threshold is not None
                else config.cognitive_depth_threshold
            )
            time_ms = (
                time_threshold_ms
                if time_threshold_ms is not None
                else config.cognitive_time_threshold_ms
            )
            cycles = (
                max_cycles if max_cycles is not None else config.cognitive_max_cycles
            )
            self.actr_resolver = ACTRResolver(config=config)
            # Will set memory reference after initialization
            self._actr_needs_memory_ref = True
        else:
            # Backward compatibility: use defaults if no config
            depth = depth_threshold if depth_threshold is not None else 3
            time_ms = time_threshold_ms if time_threshold_ms is not None else 500.0
            cycles = max_cycles if max_cycles is not None else 100
            self.actr_resolver = ACTRResolver()
            # Will set memory reference after initialization
            self._actr_needs_memory_ref = True

        self.rule_engine = RuleEngine()
        self.meta_monitor = MetaCognitiveMonitor(depth, time_ms)
        self.impasse_detector = ImpasseDetector()
        self.safety = SafetyMiddleware(safety_config)  # Safety layer

        # Unified Memory System (goal stack + learning/chunking)
        self.enable_learning = enable_learning
        if enable_learning:
            try:
                # Suppress ChromaDB Pydantic V1 warnings for Python 3.14+
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
                    self.memory = UnifiedMemory(persist_directory=chunk_store_path)
                    self.current_context_id = None
            except (RuntimeError, Exception) as e:
                # ChromaDB not available (e.g., Python 3.14+ incompatibility)
                # Note: Warning will be shown when learning is actually attempted
                self.memory = None
                self.current_context_id = None
                self.enable_learning = False  # Disable learning if ChromaDB unavailable
        else:
            self.memory = None
            self.current_context_id = None

        # Set memory reference in ACT-R resolver for semantic retrieval
        if hasattr(self, '_actr_needs_memory_ref') and self._actr_needs_memory_ref:
            self.actr_resolver.memory = self.memory

        self.config = config  # Store config for later use
        self.max_cycles = cycles
        self.current_goal: Optional[Goal] = None
        self.goal_stack: list[Goal] = []  # Stack of goals (for sub-goaling)

        # Working memory (will be initialized in solve())
        self.working_memory: Optional[WorkingMemory] = None

        # Track last ACT-R resolution for chunking
        self._last_actr_operator: Optional[Operator] = None
        self._last_actr_utility: Optional[float] = None
        self._last_actr_state: Optional[EditorState] = None

        # Evolutionary solver (fallback when ACT-R fails or pressure very high)
        self.evolution_enabled = config.evolution_enabled if config else True
        if self.evolution_enabled:
            try:
                # Create evaluator and evolutionary solver
                evaluator = CodeEvaluator()
                llm_client = self.actr_resolver.llm  # Reuse ACT-R's LLM client
                self.evolution_solver = EvolutionarySolver(
                    llm_client=llm_client,
                    evaluator=evaluator,
                    config=config,
                )
            except Exception as e:
                print(f"Warning: Failed to initialize evolutionary solver: {e}")
                self.evolution_enabled = False
                self.evolution_solver = None
        else:
            self.evolution_solver = None

    async def solve(
        self, goal: Goal, initial_state: EditorState, verbose: Union[bool, int] = 2
    ) -> tuple[bool, EditorState]:
        """
        Main entry point: solve a goal starting from initial state.

        Args:
            goal: The goal to achieve
            initial_state: Starting state
            verbose: Verbosity level (0=silent, 1=basic, 2=thinking, 3=debug) or bool for backward compat

        Returns:
            (success: bool, final_state: EditorState)
        """
        verbose_level = normalize_verbose(verbose)
        self.current_goal = goal
        self.goal_stack = [goal]
        self.working_memory = WorkingMemory(initial_state, goal)

        if should_print(verbose_level, VerbosityLevel.BASIC):
            print(f"\n🎯 GOAL: {goal.description}")
            print(f"📍 Initial State: {initial_state.working_directory}\n")

        if should_print(verbose_level, VerbosityLevel.THINKING):
            # Thinking output for goal analysis
            thinking_lines = [
                f"Goal: {goal.description}",
                f"Working directory: {initial_state.working_directory}",
                f"Open files: {len(initial_state.open_files)}",
            ]
            if initial_state.open_files:
                file_list = ", ".join(list(initial_state.open_files.keys())[:3])
                if len(initial_state.open_files) > 3:
                    file_list += f" (+{len(initial_state.open_files) - 3} more)"
                thinking_lines.append(f"Files: {file_list}")
            if initial_state.error_log:
                thinking_lines.append(f"Recent errors: {len(initial_state.error_log)}")
            print(format_thinking("Analyzing Initial State", "\n".join(thinking_lines)))
            print()

        # Run the decision cycle
        cycles = 0
        while cycles < self.max_cycles and not self._goal_achieved():
            cycles += 1

            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n--- Cycle {cycles} ---")

            # Run one decision cycle
            success = await self._decision_cycle(verbose_level)

            # Check if goal was achieved during this cycle (e.g., after fix verification)
            if self._goal_achieved():
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print(f"\n✅ Goal achieved in {cycles} cycles!")
                    if should_print(verbose_level, VerbosityLevel.THINKING):
                        print(f"\nTrace:\n{self.working_memory.get_trace()}")
                return True, self.working_memory.current_state

            if not success:
                # Stuck - goal failed
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print("\n❌ Goal failed - no progress possible")
                return False, self.working_memory.current_state

        # Check final status
        if self._goal_achieved():
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n✅ Goal achieved in {cycles} cycles!")
                if should_print(verbose_level, VerbosityLevel.THINKING):
                    print(f"\nTrace:\n{self.working_memory.get_trace()}")
            return True, self.working_memory.current_state
        else:
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n⏱️  Timeout after {cycles} cycles")
            return False, self.working_memory.current_state

    async def _decision_cycle(self, verbose: int = 2) -> bool:
        """
        Execute one Soar decision cycle.

        Args:
            verbose: Verbosity level (0-3)

        Returns:
            True if progress was made, False if stuck
        """
        # Check if goal is already achieved before starting cycle
        if self._goal_achieved():
            return True

        current_state = self.working_memory.current_state
        current_goal = self.current_goal

        # === 1. ELABORATION ===
        if should_print(verbose, VerbosityLevel.THINKING):
            thinking_lines = [
                f"Working directory: {current_state.working_directory}",
                f"Open files: {len(current_state.open_files)}",
                f"Goal: {current_goal.description[:60]}",
            ]
            if current_state.error_log:
                thinking_lines.append(f"Recent error: {current_state.error_log[-1][:50]}...")
            print(format_thinking("Analyzing Current State", "\n".join(thinking_lines)))

        # === 2. OPERATOR PROPOSAL ===
        if should_print(verbose, VerbosityLevel.BASIC):
            print(f"🔍 Proposing operators for: {current_goal.description[:60]}")

        proposed_ops = self.rule_engine.propose_operators(
            current_state, current_goal
        )

        if should_print(verbose, VerbosityLevel.BASIC):
            print(f"   Found {len(proposed_ops)} proposals")
            for op, priority in proposed_ops[:3]:  # Show top 3
                print(f"   - {op.name} (priority: {priority})")

        if should_print(verbose, VerbosityLevel.THINKING) and proposed_ops:
            # Show reasoning for operator proposals
            thinking_lines = []
            for op, priority in proposed_ops[:3]:
                thinking_lines.append(f"Rule matched: {op.name} (priority: {priority:.1f})")
            if len(proposed_ops) > 3:
                thinking_lines.append(f"... and {len(proposed_ops) - 3} more proposals")
            print(format_thinking("Evaluating Operator Proposals", "\n".join(thinking_lines)))

        # === 3. OPERATOR SELECTION / IMPASSE DETECTION ===
        impasse = self.impasse_detector.detect_impasse(proposed_ops, current_goal)

        if impasse is None:
            # Clear winner - apply operator
            operator, priority = proposed_ops[0]
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"✓ Selected: {operator.name}")

            if should_print(verbose, VerbosityLevel.THINKING):
                thinking_lines = [
                    f"Selected: {operator.name}",
                    f"Priority: {priority:.1f}",
                    f"Reasoning: Clear winner - highest priority operator",
                ]
                print(format_thinking("Operator Selection", "\n".join(thinking_lines)))

            await self._apply_operator(operator, verbose)
            self.meta_monitor.reset_timer()
            return True

        else:
            # IMPASSE - need to handle
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"⚠️  IMPASSE: {impasse.type.value}")
                print(f"   {impasse.description}")

            if should_print(verbose, VerbosityLevel.THINKING):
                thinking_lines = [
                    f"Type: {impasse.type.value}",
                    f"Description: {impasse.description}",
                    f"Operators involved: {len(impasse.operators)}",
                ]
                print(format_thinking("Impasse Detected", "\n".join(thinking_lines)))

            self.meta_monitor.increment_impasse_count()
            return await self._handle_impasse(impasse, proposed_ops, verbose)

    async def _handle_impasse(
        self,
        impasse: Impasse,
        proposed_ops: list[tuple[Operator, float]],
        verbose: int = 2,
    ) -> bool:
        """
        Handle an impasse.

        Strategy:
        1. Calculate cognitive metrics
        2. Check if pressure is too high
        3. If yes: Trigger ACT-R fallback (Phase 4)
        4. If no: Create sub-goal and recurse

        Args:
            impasse: The impasse encountered
            proposed_ops: Operators that led to impasse
            verbose: Print status

        Returns:
            True if progress made, False if stuck
        """
        # Calculate current cognitive pressure
        ambiguity = self.meta_monitor.calculate_operator_ambiguity(proposed_ops)
        metrics = CognitiveMetrics(
            goal_depth=self.current_goal.depth(),
            time_in_state_ms=self.meta_monitor.get_time_in_state_ms(),
            impasse_count=self.meta_monitor.total_impasses,
            operator_ambiguity=ambiguity,
        )

        if should_print(verbose, VerbosityLevel.BASIC):
            print(f"   {self.meta_monitor.get_status_summary(metrics)}")

        if should_print(verbose, VerbosityLevel.THINKING):
            print(format_thinking("Checking Cognitive Pressure", self.meta_monitor.get_thinking_summary(metrics)))

        # Check if we should fallback
        pressure = self.meta_monitor.calculate_pressure(metrics)
        should_fallback = self.meta_monitor.should_trigger_fallback(metrics)

        # Very high pressure (>= 0.9) or ACT-R failure -> try evolutionary solver
        if (pressure >= 0.9 or should_fallback) and self.evolution_enabled and self.evolution_solver:
            if self._goal_involves_code_fixing():
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"\n🧬 VERY HIGH PRESSURE ({pressure:.2f}) - TRIGGERING EVOLUTIONARY SOLVER")
                return await self._try_evolutionary_fallback(verbose)

        if should_fallback:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"\n🔴 COGNITIVE OVERLOAD - TRIGGERING ACT-R FALLBACK")

            if should_print(verbose, VerbosityLevel.THINKING):
                thinking_lines = [
                    f"Pressure threshold exceeded (≥0.7)",
                    f"Switching from Soar (System 2) to ACT-R (System 1)",
                    f"Reasoning: Cognitive load too high for symbolic reasoning",
                ]
                print(format_thinking("Switching to ACT-R Mode", "\n".join(thinking_lines)))

            # Use ACT-R to select best operator
            if impasse.type == ImpasseType.TIE and impasse.operators:
                result = await self.actr_resolver.resolve(
                    impasse.operators,
                    self.working_memory.current_state,
                    self.current_goal,
                    verbose=verbose,
                    working_memory=self.working_memory,
                    history_penalty_multiplier=self.config.cognitive_history_penalty_multiplier if self.config else 2.0,
                )

                if result:
                    operator, utility = result

                    # Track for chunking
                    if self.enable_learning:
                        self._last_actr_operator = operator
                        self._last_actr_utility = utility
                        self._last_actr_state = self.working_memory.current_state.model_copy(deep=True)

                    await self._apply_operator(operator, verbose)

                    # LEARNING: If operator succeeded, create chunk and store resolution
                    if self.enable_learning and self.memory:
                        last_transition = self.working_memory.history[-1] if self.working_memory.history else None
                        if last_transition and last_transition.success:
                            chunk = create_chunk_from_success(
                                state=self._last_actr_state,
                                operator=self._last_actr_operator,
                                goal=self.current_goal.description,
                                utility=self._last_actr_utility,
                            )
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   💾 Learning: Created chunk {chunk.id[:8]}...")
                            self.memory.store_chunk(chunk)

                            # Store resolution in current context
                            self.memory.update_context_resolution(
                                operator=operator.name if operator else None,
                                reasoning=f"ACT-R selected with utility {self._last_actr_utility:.2f}"
                            )

                    return True
                else:
                    if should_print(verbose, VerbosityLevel.BASIC):
                        print(f"   ACT-R fallback failed - no LLM response")
                    return False
            elif impasse.type == ImpasseType.NO_CHANGE:
                # NO_CHANGE impasse - generate operators using LLM
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   🤖 Generating operators using ACT-R...")

                generated_ops = await self.actr_resolver.generate_operators(
                    self.working_memory.current_state,
                    self.current_goal,
                    verbose=verbose,
                )

                if generated_ops:
                    # Evaluate the generated operators and pick the best
                    penalty_mult = self.config.cognitive_history_penalty_multiplier if self.config else 2.0
                    result = await self.actr_resolver.resolve(
                        generated_ops,
                        self.working_memory.current_state,
                        self.current_goal,
                        verbose=verbose,
                        working_memory=self.working_memory,
                        history_penalty_multiplier=penalty_mult,
                    )

                    if result:
                        operator, utility = result

                        # Track for chunking
                        if self.enable_learning:
                            self._last_actr_operator = operator
                            self._last_actr_utility = utility
                            self._last_actr_state = self.working_memory.current_state.model_copy(deep=True)

                        await self._apply_operator(operator, verbose)

                        # LEARNING: If operator succeeded, create chunk and store resolution
                        if self.enable_learning and self.memory:
                            last_transition = self.working_memory.history[-1] if self.working_memory.history else None
                            if last_transition and last_transition.success:
                                chunk = create_chunk_from_success(
                                    state=self._last_actr_state,
                                    operator=self._last_actr_operator,
                                    goal=self.current_goal.description,
                                    utility=self._last_actr_utility,
                                )
                                if should_print(verbose, VerbosityLevel.BASIC):
                                    print(f"   💾 Learning: Created chunk {chunk.id[:8]}...")
                                self.memory.store_chunk(chunk)

                                # Store resolution in current context
                                self.memory.update_context_resolution(
                                    operator=operator.name if operator else None,
                                    reasoning=f"ACT-R selected with utility {self._last_actr_utility:.2f}"
                                )

                        return True
                    else:
                        # ACT-R failed - try evolutionary solver as fallback
                        if self.evolution_enabled and self.evolution_solver and self._goal_involves_code_fixing():
                            return await self._try_evolutionary_fallback(verbose)
                        else:
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   ⚠️  ACT-R failed to evaluate generated operators")
                                print(f"   ℹ️  LLM may be unavailable. Symbolic reasoning only mode.")
                            return False
                else:
                    # ACT-R failed to generate - try evolutionary solver as fallback
                    if self.evolution_enabled and self.evolution_solver and self._goal_involves_code_fixing():
                        return await self._try_evolutionary_fallback(verbose)
                    else:
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   ⚠️  ACT-R failed to generate operators")
                            print(f"   ℹ️  LLM unavailable. Cannot proceed without rules or LLM.")
                            print(f"   💡 Tip: Start Ollama with 'ollama serve' for LLM support")
                        return False
            else:
                # Other impasse types - no operators to rate
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   No operators to evaluate")
                return False

        else:
            # Pressure OK - but for NO_CHANGE, we still need ACT-R to generate operators
            if impasse.type == ImpasseType.NO_CHANGE:
                # No operators - use ACT-R to generate them
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   🤖 Generating operators using ACT-R (low pressure)...")

                if should_print(verbose, VerbosityLevel.THINKING):
                    thinking_lines = [
                        f"Pressure is low (<0.7)",
                        f"Using ACT-R to generate operators (no rules matched)",
                        f"Reasoning: Need LLM to suggest operators when symbolic rules fail",
                    ]
                    print(format_thinking("Generating Operators with ACT-R", "\n".join(thinking_lines)))

                generated_ops = await self.actr_resolver.generate_operators(
                    self.working_memory.current_state,
                    self.current_goal,
                    verbose=verbose,
                )

                if generated_ops:
                    # Evaluate and pick the best
                    penalty_mult = self.config.cognitive_history_penalty_multiplier if self.config else 2.0
                    result = await self.actr_resolver.resolve(
                        generated_ops,
                        self.working_memory.current_state,
                        self.current_goal,
                        verbose=verbose,
                        working_memory=self.working_memory,
                        history_penalty_multiplier=penalty_mult,
                    )

                    if result:
                        operator, utility = result
                        await self._apply_operator(operator, verbose)
                        return True
                    else:
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   ACT-R failed to evaluate generated operators")
                        return False
                else:
                    if should_print(verbose, VerbosityLevel.BASIC):
                        print(f"   ⚠️  ACT-R failed to generate operators")
                        print(f"   ℹ️  LLM unavailable. Cannot proceed without rules or LLM.")
                        print(f"   💡 Tip: Start Ollama with 'ollama serve' for LLM support")
                    return False

            elif impasse.type == ImpasseType.TIE:
                # Multiple equal operators - for now, just pick first
                # (In Phase 4, ACT-R will rate them)
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   Breaking tie by selecting first operator")
                if should_print(verbose, VerbosityLevel.THINKING):
                    thinking_lines = [
                        f"Multiple operators with equal priority",
                        f"Selecting first operator as tie-breaker",
                    ]
                    print(format_thinking("Resolving Tie", "\n".join(thinking_lines)))
                operator, _ = impasse.operators[0]
                await self._apply_operator(operator, verbose)
                return True

            else:
                # Other impasse types - create sub-goal
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   Creating sub-goal to resolve impasse")
                if should_print(verbose, VerbosityLevel.THINKING):
                    thinking_lines = [
                        f"Creating sub-goal to resolve {impasse.type.value} impasse",
                        f"Reasoning: Pressure is low, can continue with symbolic reasoning",
                    ]
                    print(format_thinking("Creating Sub-Goal", "\n".join(thinking_lines)))
                subgoal = Goal(
                    description=f"Resolve {impasse.type.value} impasse",
                    parent_goal=self.current_goal,
                )
                self._push_goal(subgoal)
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   ↳ New sub-goal: {subgoal.description}")
                return True

    async def _apply_operator(self, operator: Operator, verbose: int = 2) -> None:
        """
        Apply an operator and update working memory.

        Args:
            operator: Operator to execute
            verbose: Verbosity level (0-3)
        """
        if should_print(verbose, VerbosityLevel.BASIC):
            print(f"⚙️  Applying: {operator.name}")

        if should_print(verbose, VerbosityLevel.THINKING):
            thinking_lines = [
                f"Operator: {operator.name}",
                f"Expected: Execute operation and update state",
            ]
            if hasattr(operator, 'path'):
                thinking_lines.append(f"Target: {operator.path}")
            print(format_thinking("Applying Operator", "\n".join(thinking_lines)))

        current_state = self.working_memory.current_state

        # Execute operator
        result = await operator.execute(current_state)

        if result.success:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"   ✓ {result.output}")

            # Update working memory
            new_state = result.new_state or current_state
            self.working_memory.record_transition(
                operator, result, new_state, self.current_goal
            )

            # Check if running code successfully means goal is achieved
            from cognitive_hydraulics.operators.exec_ops import OpRunCode
            if isinstance(operator, OpRunCode):
                # If code runs successfully (no errors) and goal mentions "fix" or "run without errors"
                # AND tests pass (check stdout for "All tests passed"), then the goal is achieved
                if (self.current_goal and
                    ("fix" in self.current_goal.description.lower() or
                     "run without errors" in self.current_goal.description.lower() or
                     "runs without errors" in self.current_goal.description.lower() or
                     "sorts correctly" in self.current_goal.description.lower()) and
                    not result.error and
                    len(new_state.error_log) == 0):  # No errors in error_log

                    # Check if file has test functions - if so, tests must pass
                    has_test_function = False
                    if hasattr(operator, 'path') and operator.path in new_state.open_files:
                        file_content = new_state.open_files[operator.path].content
                        # Check for test functions (def test_ or if __name__ == "__main__")
                        if "def test_" in file_content or 'if __name__ == "__main__"' in file_content:
                            has_test_function = True

                    output_text = result.output or ""
                    stdout_text = ""
                    if "STDOUT:" in output_text:
                        stdout_text = output_text.split("STDOUT:")[1].split("STDERR:")[0] if "STDERR:" in output_text else output_text.split("STDOUT:")[1]

                    # If tests exist, they must pass
                    if has_test_function:
                        if "All tests passed" in stdout_text:
                            self.current_goal.status = "success"
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   🎯 Goal achieved: Code runs without errors and tests pass!")
                        else:
                            # Tests exist but didn't pass or weren't run
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   ⚠️  Tests did not pass or were not executed - goal not achieved")
                            # Don't set goal to success
                    else:
                        # No test functions - just check that code runs without errors
                        self.current_goal.status = "success"
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   🎯 Goal achieved: Code runs without errors!")

            # If a fix was applied, verify it by running the code
            from cognitive_hydraulics.operators.file_ops import OpApplyFix
            from cognitive_hydraulics.operators.exec_ops import OpRunCode

            if isinstance(operator, OpApplyFix) and hasattr(operator, 'path') and operator.path.endswith('.py'):
                if should_print(verbose, VerbosityLevel.BASIC):
                    print(f"   🔍 Verifying fix by running {operator.path}...")

                # Run the code to verify the fix
                verify_op = OpRunCode(operator.path)
                verify_result = await verify_op.execute(new_state)

                # Check if verification actually passed
                verification_passed = False

                # First check: code must run without exceptions (success=True, no error, no errors in log)
                # Note: AssertionError from test failures will make success=False and add to error_log
                if verify_result.success and not verify_result.error and len(new_state.error_log) == 0:
                    # Check if file has test functions - if so, tests must pass
                    has_test_function = False
                    if operator.path in new_state.open_files:
                        file_content = new_state.open_files[operator.path].content
                        if "def test_" in file_content or 'if __name__ == "__main__"' in file_content:
                            has_test_function = True

                    output_text = verify_result.output or ""
                    stdout_text = ""
                    if "STDOUT:" in output_text:
                        stdout_text = output_text.split("STDOUT:")[1].split("STDERR:")[0] if "STDERR:" in output_text else output_text.split("STDOUT:")[1]

                    if has_test_function:
                        # Tests exist - they must pass
                        if "All tests passed" in stdout_text:
                            verification_passed = True
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   ✅ Verification passed: Code runs without errors and tests pass")
                        else:
                            # Tests exist but didn't pass or weren't executed
                            verification_passed = False
                            if should_print(verbose, VerbosityLevel.BASIC):
                                print(f"   ⚠️  Verification failed: Tests did not pass or were not executed")
                                if stdout_text:
                                    print(f"      Output: {stdout_text[:200]}")
                                # Check if there's an error in the result
                                if verify_result.error:
                                    print(f"      Error: {verify_result.error}")
                                # Check error_log for AssertionError
                                if new_state.error_log:
                                    print(f"      Error log: {new_state.error_log[-1]}")
                    else:
                        # No test functions - just check that code runs without errors
                        verification_passed = True
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   ✅ Verification passed: Code runs without errors (no tests to verify)")
                else:
                    # Code failed to run or had errors (including AssertionError from test failures)
                    verification_passed = False
                    if should_print(verbose, VerbosityLevel.BASIC):
                        print(f"   ⚠️  Verification failed: Code execution failed or tests failed")
                        if verify_result.error:
                            print(f"      Error: {verify_result.error}")
                        # Check error_log for AssertionError or other errors
                        if new_state.error_log:
                            last_error = new_state.error_log[-1]
                            print(f"      Error log: {last_error}")
                            # If AssertionError, tests failed - goal not achieved
                            if "AssertionError" in last_error:
                                if should_print(verbose, VerbosityLevel.BASIC):
                                    print(f"      ❌ Tests failed - fix did not work correctly")

                if verification_passed:
                    # Update goal status to success if goal mentions fixing/running
                    if self.current_goal and ("fix" in self.current_goal.description.lower() or
                                               "run" in self.current_goal.description.lower() or
                                               "sort" in self.current_goal.description.lower() or
                                               "sorts correctly" in self.current_goal.description.lower()):
                        self.current_goal.status = "success"
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   🎯 Goal achieved: {self.current_goal.description[:50]}...")
                else:
                    if should_print(verbose, VerbosityLevel.BASIC):
                        print(f"   ⚠️  Verification failed: {verify_result.error or 'Code still has errors or tests failed'}")

        else:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"   ✗ {result.error}")

            # Record failure - but use new_state if available (it may contain error_log updates)
            new_state = result.new_state or current_state
            self.working_memory.record_transition(
                operator, result, new_state, self.current_goal
            )

    def _goal_achieved(self) -> bool:
        """Check if current goal is achieved."""
        if not self.current_goal:
            return True

        # For now, simple heuristic: goal achieved if status is "success"
        # In practice, would need more sophisticated goal checking
        return self.current_goal.status == "success"

    def _create_state_snapshot(self, state: EditorState) -> str:
        """Create a text snapshot of the current state for memory storage."""
        parts = [f"Working dir: {state.working_directory}"]

        if state.open_files:
            files = list(state.open_files.keys())
            parts.append(f"Open files: {', '.join(files[:5])}")
            if len(files) > 5:
                parts.append(f"  (+{len(files) - 5} more)")

        if state.error_log:
            parts.append(f"Recent errors: {len(state.error_log)}")
            if state.error_log:
                parts.append(f"  Last error: {state.error_log[-1][:100]}")

        if state.last_output:
            parts.append(f"Last output: {state.last_output[:100]}...")

        return "\n".join(parts)

    def _push_goal(self, goal: Goal) -> None:
        """Push a new goal onto the stack."""
        self.goal_stack.append(goal)
        self.current_goal = goal

        # Persist to memory if available
        if self.memory and self.working_memory:
            state_snapshot = self._create_state_snapshot(self.working_memory.current_state)
            context_id = self.memory.push_context(
                goal=goal.description,
                state=state_snapshot,
                parent_id=self.current_context_id
            )
            self.current_context_id = context_id

    def _pop_goal(self) -> Optional[Goal]:
        """Pop current goal from stack."""
        if len(self.goal_stack) > 1:
            old_goal = self.goal_stack.pop()
            self.current_goal = self.goal_stack[-1]

            # Persist to memory if available
            if self.memory:
                status = "success" if old_goal.status == "success" else "failed"
                self.current_context_id = self.memory.pop_context(status=status)

            return self.current_goal
        return None

    def get_statistics(self) -> dict:
        """Get statistics about the reasoning session."""
        if not self.working_memory:
            return {}

        return {
            "total_transitions": len(self.working_memory),
            "successful_ops": sum(
                1 for t in self.working_memory.history if t.result.success
            ),
            "failed_ops": sum(
                1 for t in self.working_memory.history if not t.result.success
            ),
            "total_impasses": self.meta_monitor.total_impasses,
            "max_goal_depth": max(
                (t.goal_at_time.depth() for t in self.working_memory.history),
                default=0,
            ),
        }

    def _goal_involves_code_fixing(self) -> bool:
        """
        Check if the current goal involves fixing code bugs.

        Returns:
            True if goal mentions keywords related to code fixing
        """
        if not self.current_goal:
            return False

        goal_lower = self.current_goal.description.lower()
        keywords = ["fix", "bug", "error", "sort", "correct", "repair", "debug"]
        return any(keyword in goal_lower for keyword in keywords)

    def _extract_error_context(self, state: EditorState) -> str:
        """
        Extract error context for evolutionary solver.

        Args:
            state: Current state

        Returns:
            Formatted error context string
        """
        parts = []

        # Add error from error_log
        if state.error_log:
            parts.append("ERROR:")
            parts.append(state.error_log[-1])
            parts.append("")

        # Add relevant code from open files
        if state.open_files:
            parts.append("CODE:")
            for filename, file_content in state.open_files.items():
                if filename.endswith('.py'):
                    parts.append(f"File: {filename}")
                    # Include relevant lines around error if available
                    code_lines = file_content.content.split('\n')
                    # Show first 50 lines or all if less
                    code_snippet = '\n'.join(code_lines[:50])
                    if len(code_lines) > 50:
                        code_snippet += "\n... (truncated)"
                    parts.append(code_snippet)
                    parts.append("")

        # Add last output if available
        if state.last_output:
            parts.append("LAST OUTPUT:")
            parts.append(state.last_output[:500])  # Limit output size
            parts.append("")

        return "\n".join(parts)

    async def _try_evolutionary_fallback(self, verbose: int = 2) -> bool:
        """
        Try evolutionary solver as fallback when ACT-R fails or pressure is very high.

        Args:
            verbose: Verbosity level

        Returns:
            True if evolutionary solver found and applied a fix, False otherwise
        """
        if not self.evolution_solver or not self.current_goal:
            return False

        state = self.working_memory.current_state

        # Extract error context
        error_context = self._extract_error_context(state)

        # Find the Python file to fix
        target_file = None
        original_code = None
        test_code = None

        for filename, file_content in state.open_files.items():
            if filename.endswith('.py'):
                target_file = filename
                code = file_content.content

                # Try to separate test code from main code
                # Look for test functions or if __name__ == "__main__"
                if 'def test_' in code or 'if __name__ == "__main__"' in code:
                    # For simplicity, use full code as both code and test_code
                    # The evaluator will handle it
                    original_code = code
                    test_code = code  # Tests are embedded
                else:
                    original_code = code
                    test_code = None
                break

        if not target_file or not original_code:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"   ⚠️  No Python file found for evolutionary solver")
            return False

        # Run evolutionary solver
        best_candidate = await self.evolution_solver.evolve(
            error_context=error_context,
            goal=self.current_goal.description,
            original_code=original_code,
            test_code=test_code,
            verbose=verbose,
        )

        if not best_candidate:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"   ⚠️  Evolutionary solver did not find a solution")
            return False

        # Apply the fix using OpApplyFix
        from cognitive_hydraulics.operators.file_ops import OpApplyFix

        fix_op = OpApplyFix(
            path=target_file,
            fix_description=best_candidate.hypothesis,
            fixed_content=best_candidate.code_patch,
        )

        if should_print(verbose, VerbosityLevel.BASIC):
            print(f"   ✅ Applying evolutionary fix: {best_candidate.hypothesis}")

        await self._apply_operator(fix_op, verbose)

        return True

    def __repr__(self) -> str:
        return (
            f"CognitiveAgent(rules={len(self.rule_engine.rules)}, "
            f"goal_depth={self.current_goal.depth() if self.current_goal else 0})"
        )


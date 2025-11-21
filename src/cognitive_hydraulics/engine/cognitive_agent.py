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
from cognitive_hydraulics.safety.middleware import SafetyMiddleware, SafetyConfig
from cognitive_hydraulics.memory.chroma_store import ChunkStore
from cognitive_hydraulics.memory.chunk import create_chunk_from_success
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
        else:
            # Backward compatibility: use defaults if no config
            depth = depth_threshold if depth_threshold is not None else 3
            time_ms = time_threshold_ms if time_threshold_ms is not None else 500.0
            cycles = max_cycles if max_cycles is not None else 100
            self.actr_resolver = ACTRResolver()

        self.rule_engine = RuleEngine()
        self.meta_monitor = MetaCognitiveMonitor(depth, time_ms)
        self.impasse_detector = ImpasseDetector()
        self.safety = SafetyMiddleware(safety_config)  # Safety layer

        # Learning/Chunking system
        self.enable_learning = enable_learning
        if enable_learning:
            try:
                # Suppress ChromaDB Pydantic V1 warnings for Python 3.14+
                import warnings
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
                    self.chunk_store = ChunkStore(persist_directory=chunk_store_path)
            except (RuntimeError, Exception) as e:
                # ChromaDB not available (e.g., Python 3.14+ incompatibility)
                # Note: Warning will be shown when learning is actually attempted
                self.chunk_store = None
                self.enable_learning = False  # Disable learning if ChromaDB unavailable
        else:
            self.chunk_store = None

        self.max_cycles = cycles
        self.current_goal: Optional[Goal] = None
        self.goal_stack: list[Goal] = []  # Stack of goals (for sub-goaling)

        # Working memory (will be initialized in solve())
        self.working_memory: Optional[WorkingMemory] = None

        # Track last ACT-R resolution for chunking
        self._last_actr_operator: Optional[Operator] = None
        self._last_actr_utility: Optional[float] = None
        self._last_actr_state: Optional[EditorState] = None

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
        if self.meta_monitor.should_trigger_fallback(metrics):
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
                )

                if result:
                    operator, utility = result

                    # Track for chunking
                    if self.enable_learning:
                        self._last_actr_operator = operator
                        self._last_actr_utility = utility
                        self._last_actr_state = self.working_memory.current_state.model_copy(deep=True)

                    await self._apply_operator(operator, verbose)

                    # LEARNING: If operator succeeded, create chunk
                    if self.enable_learning and self.chunk_store:
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
                            self.chunk_store.store_chunk(chunk)

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
                    result = await self.actr_resolver.resolve(
                        generated_ops,
                        self.working_memory.current_state,
                        self.current_goal,
                        verbose=verbose,
                    )

                    if result:
                        operator, utility = result

                        # Track for chunking
                        if self.enable_learning:
                            self._last_actr_operator = operator
                            self._last_actr_utility = utility
                            self._last_actr_state = self.working_memory.current_state.model_copy(deep=True)

                        await self._apply_operator(operator, verbose)

                        # LEARNING: If operator succeeded, create chunk
                        if self.enable_learning and self.chunk_store:
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
                                self.chunk_store.store_chunk(chunk)

                        return True
                    else:
                        if should_print(verbose, VerbosityLevel.BASIC):
                            print(f"   ⚠️  ACT-R failed to evaluate generated operators")
                            print(f"   ℹ️  LLM may be unavailable. Symbolic reasoning only mode.")
                        return False
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

        else:
            if should_print(verbose, VerbosityLevel.BASIC):
                print(f"   ✗ {result.error}")

            # Record failure
            self.working_memory.record_transition(
                operator, result, current_state, self.current_goal
            )

    def _goal_achieved(self) -> bool:
        """Check if current goal is achieved."""
        if not self.current_goal:
            return True

        # For now, simple heuristic: goal achieved if status is "success"
        # In practice, would need more sophisticated goal checking
        return self.current_goal.status == "success"

    def _push_goal(self, goal: Goal) -> None:
        """Push a new goal onto the stack."""
        self.goal_stack.append(goal)
        self.current_goal = goal

    def _pop_goal(self) -> Optional[Goal]:
        """Pop current goal from stack."""
        if len(self.goal_stack) > 1:
            self.goal_stack.pop()
            self.current_goal = self.goal_stack[-1]
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

    def __repr__(self) -> str:
        return (
            f"CognitiveAgent(rules={len(self.rule_engine.rules)}, "
            f"goal_depth={self.current_goal.depth() if self.current_goal else 0})"
        )


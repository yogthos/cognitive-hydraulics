"""Main cognitive agent implementing the Soar decision cycle."""

from __future__ import annotations

from typing import Optional
import asyncio

from cognitive_hydraulics.core.state import EditorState, Goal
from cognitive_hydraulics.core.operator import Operator, OperatorResult
from cognitive_hydraulics.core.working_memory import WorkingMemory
from cognitive_hydraulics.engine.rule_engine import RuleEngine
from cognitive_hydraulics.engine.meta_monitor import MetaCognitiveMonitor, CognitiveMetrics
from cognitive_hydraulics.engine.impasse import ImpasseDetector, Impasse, ImpasseType
from cognitive_hydraulics.engine.actr_resolver import ACTRResolver
from cognitive_hydraulics.safety.middleware import SafetyMiddleware, SafetyConfig
from cognitive_hydraulics.memory.chroma_store import ChunkStore
from cognitive_hydraulics.memory.chunk import create_chunk_from_success
from typing import TYPE_CHECKING

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
        self.chunk_store = ChunkStore(persist_directory=chunk_store_path) if enable_learning else None

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
        self, goal: Goal, initial_state: EditorState, verbose: bool = True
    ) -> tuple[bool, EditorState]:
        """
        Main entry point: solve a goal starting from initial state.

        Args:
            goal: The goal to achieve
            initial_state: Starting state
            verbose: Print decision trace

        Returns:
            (success: bool, final_state: EditorState)
        """
        self.current_goal = goal
        self.goal_stack = [goal]
        self.working_memory = WorkingMemory(initial_state, goal)

        if verbose:
            print(f"\n🎯 GOAL: {goal.description}")
            print(f"📍 Initial State: {initial_state.working_directory}\n")

        # Run the decision cycle
        cycles = 0
        while cycles < self.max_cycles and not self._goal_achieved():
            cycles += 1

            if verbose:
                print(f"\n--- Cycle {cycles} ---")

            # Run one decision cycle
            success = await self._decision_cycle(verbose)

            if not success:
                # Stuck - goal failed
                if verbose:
                    print("\n❌ Goal failed - no progress possible")
                return False, self.working_memory.current_state

        # Check final status
        if self._goal_achieved():
            if verbose:
                print(f"\n✅ Goal achieved in {cycles} cycles!")
                print(f"\nTrace:\n{self.working_memory.get_trace()}")
            return True, self.working_memory.current_state
        else:
            if verbose:
                print(f"\n⏱️  Timeout after {cycles} cycles")
            return False, self.working_memory.current_state

    async def _decision_cycle(self, verbose: bool = True) -> bool:
        """
        Execute one Soar decision cycle.

        Returns:
            True if progress was made, False if stuck
        """
        current_state = self.working_memory.current_state
        current_goal = self.current_goal

        # === 1. ELABORATION ===
        # (Currently minimal - just use current state)

        # === 2. OPERATOR PROPOSAL ===
        if verbose:
            print(f"🔍 Proposing operators for: {current_goal.description[:60]}")

        proposed_ops = self.rule_engine.propose_operators(
            current_state, current_goal
        )

        if verbose:
            print(f"   Found {len(proposed_ops)} proposals")
            for op, priority in proposed_ops[:3]:  # Show top 3
                print(f"   - {op.name} (priority: {priority})")

        # === 3. OPERATOR SELECTION / IMPASSE DETECTION ===
        impasse = self.impasse_detector.detect_impasse(proposed_ops, current_goal)

        if impasse is None:
            # Clear winner - apply operator
            operator, priority = proposed_ops[0]
            if verbose:
                print(f"✓ Selected: {operator.name}")

            await self._apply_operator(operator, verbose)
            self.meta_monitor.reset_timer()
            return True

        else:
            # IMPASSE - need to handle
            if verbose:
                print(f"⚠️  IMPASSE: {impasse.type.value}")
                print(f"   {impasse.description}")

            self.meta_monitor.increment_impasse_count()
            return await self._handle_impasse(impasse, proposed_ops, verbose)

    async def _handle_impasse(
        self,
        impasse: Impasse,
        proposed_ops: list[tuple[Operator, float]],
        verbose: bool = True,
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

        if verbose:
            print(f"   {self.meta_monitor.get_status_summary(metrics)}")

        # Check if we should fallback
        if self.meta_monitor.should_trigger_fallback(metrics):
            if verbose:
                print(f"\n🔴 COGNITIVE OVERLOAD - TRIGGERING ACT-R FALLBACK")

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
                            if verbose:
                                print(f"   💾 Learning: Created chunk {chunk.id[:8]}...")
                            self.chunk_store.store_chunk(chunk)

                    return True
                else:
                    if verbose:
                        print(f"   ACT-R fallback failed - no LLM response")
                    return False
            elif impasse.type == ImpasseType.NO_CHANGE:
                # NO_CHANGE impasse - generate operators using LLM
                if verbose:
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
                                if verbose:
                                    print(f"   💾 Learning: Created chunk {chunk.id[:8]}...")
                                self.chunk_store.store_chunk(chunk)

                        return True
                    else:
                        if verbose:
                            print(f"   ⚠️  ACT-R failed to evaluate generated operators")
                            print(f"   ℹ️  LLM may be unavailable. Symbolic reasoning only mode.")
                        return False
                else:
                    if verbose:
                        print(f"   ⚠️  ACT-R failed to generate operators")
                        print(f"   ℹ️  LLM unavailable. Cannot proceed without rules or LLM.")
                        print(f"   💡 Tip: Start Ollama with 'ollama serve' for LLM support")
                    return False
            else:
                # Other impasse types - no operators to rate
                if verbose:
                    print(f"   No operators to evaluate")
                return False

        else:
            # Pressure OK - but for NO_CHANGE, we still need ACT-R to generate operators
            if impasse.type == ImpasseType.NO_CHANGE:
                # No operators - use ACT-R to generate them
                if verbose:
                    print(f"   🤖 Generating operators using ACT-R (low pressure)...")

                generated_ops = await self.actr_resolver.generate_operators(
                    self.working_memory.current_state,
                    self.current_goal,
                    verbose=verbose,
                )

                if generated_ops:
                    # Evaluate and pick the best
                    result = await self.actr_resolver.resolve(
                        generated_ops,
                        self.working_memory.current_state,
                        self.current_goal,
                        verbose=verbose,
                    )

                    if result:
                        operator, utility = result
                        await self._apply_operator(operator, verbose)
                        return True
                    else:
                        if verbose:
                            print(f"   ACT-R failed to evaluate generated operators")
                        return False
                else:
                    if verbose:
                        print(f"   ⚠️  ACT-R failed to generate operators")
                        print(f"   ℹ️  LLM unavailable. Cannot proceed without rules or LLM.")
                        print(f"   💡 Tip: Start Ollama with 'ollama serve' for LLM support")
                    return False

            elif impasse.type == ImpasseType.TIE:
                # Multiple equal operators - for now, just pick first
                # (In Phase 4, ACT-R will rate them)
                if verbose:
                    print(f"   Breaking tie by selecting first operator")

                operator = impasse.operators[0]
                await self._apply_operator(operator, verbose)
                return True

            else:
                # Other impasse types - create sub-goal
                if verbose:
                    print(f"   Creating sub-goal to resolve impasse")

                subgoal = self.impasse_detector.create_subgoal_from_impasse(impasse)
                self._push_goal(subgoal)

                if verbose:
                    print(f"   ↳ New sub-goal: {subgoal.description}")

                return True

    async def _apply_operator(self, operator: Operator, verbose: bool = True) -> None:
        """
        Apply an operator and update working memory.

        Args:
            operator: Operator to execute
            verbose: Print status
        """
        if verbose:
            print(f"⚙️  Applying: {operator.name}")

        current_state = self.working_memory.current_state

        # Execute operator
        result = await operator.execute(current_state)

        if result.success:
            if verbose:
                print(f"   ✓ {result.output}")

            # Update working memory
            new_state = result.new_state or current_state
            self.working_memory.record_transition(
                operator, result, new_state, self.current_goal
            )

        else:
            if verbose:
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


"""Evolutionary solver for code fixes using genetic algorithm approach."""

from __future__ import annotations

from typing import List, Optional, Tuple
from cognitive_hydraulics.engine.evaluator import CodeEvaluator, EvaluationResult
from cognitive_hydraulics.llm.client import LLMClient
from cognitive_hydraulics.llm.schemas import CodeCandidate, PopulationProposal
from cognitive_hydraulics.llm.prompts import PromptTemplates
from cognitive_hydraulics.core.verbosity import should_print, normalize_verbose, format_thinking, VerbosityLevel
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from cognitive_hydraulics.config.settings import Config


class EvolutionarySolver:
    """
    Evolutionary solver that evolves code fixes through generations.

    Uses genetic algorithm approach:
    1. Generate diverse population of candidates
    2. Evaluate fitness of each candidate
    3. Select best and mutate based on feedback
    4. Repeat until perfect solution found or max generations reached
    """

    def __init__(
        self,
        llm_client: LLMClient,
        evaluator: CodeEvaluator,
        config: Optional["Config"] = None,
    ):
        """
        Initialize evolutionary solver.

        Args:
            llm_client: LLM client for generating/mutating candidates
            evaluator: Code evaluator for fitness function
            config: Configuration object (if None, uses defaults)
        """
        self.llm = llm_client
        self.evaluator = evaluator
        self.config = config

        # Get config values
        if config:
            self.population_size = config.evolution_population_size
            self.max_generations = config.evolution_max_generations
        else:
            self.population_size = 3  # Default
            self.max_generations = 3  # Default

    async def generate_population(
        self, error_context: str, goal: str, n: Optional[int] = None
    ) -> List[CodeCandidate]:
        """
        Generate a diverse population of code fix candidates.

        Args:
            error_context: Error message and code context
            goal: Goal description
            n: Number of candidates (defaults to population_size)

        Returns:
            List of code candidates
        """
        n = n or self.population_size

        prompt = PromptTemplates.generate_population_prompt(
            error_context=error_context,
            goal=goal,
            n=n,
        )

        try:
            response = await self.llm.structured_query(
                prompt=prompt,
                response_schema=PopulationProposal,
                system_prompt=PromptTemplates.SYSTEM_PROMPT,
                verbose=False,
            )

            if response and response.candidates:
                return response.candidates[:n]  # Limit to requested size
            return []

        except Exception as e:
            print(f"Warning: Failed to generate population: {e}")
            return []

    async def evaluate_candidates(
        self,
        candidates: List[CodeCandidate],
        original_code: str,
        test_code: Optional[str] = None,
        verbose: Union[bool, int] = 2,
    ) -> List[Tuple[CodeCandidate, int]]:
        """
        Evaluate all candidates and return scores.

        Args:
            candidates: List of candidates to evaluate
            original_code: Original code (for context, not used in evaluation)
            test_code: Optional test code to run
            verbose: Verbosity level

        Returns:
            List of (candidate, score) tuples, sorted by score (highest first)
        """
        verbose_level = normalize_verbose(verbose)
        results = []

        if should_print(verbose_level, VerbosityLevel.BASIC):
            print(f"   🧬 Evaluating {len(candidates)} candidates...")

        for i, candidate in enumerate(candidates, 1):
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"      Candidate {i}: {candidate.hypothesis}")

            # Evaluate the candidate
            result = self.evaluator.evaluate(
                code=candidate.code_patch,
                test_code=test_code,
            )

            results.append((candidate, result.score))

            if should_print(verbose_level, VerbosityLevel.BASIC):
                status = "✓" if result.score == 100 else "✗"
                print(f"         {status} Score: {result.score}/100")
                if result.error_message:
                    print(f"         Error: {result.error_message[:100]}")

            if should_print(verbose_level, VerbosityLevel.THINKING):
                thinking_lines = [
                    f"Hypothesis: {candidate.hypothesis}",
                    f"Score: {result.score}/100",
                    f"Syntax: {'✓' if result.syntax_valid else '✗'}",
                    f"Runtime: {'✓' if result.runtime_valid else '✗'}",
                    f"Correctness: {'✓' if result.correctness_valid else '✗'}",
                ]
                if result.error_message:
                    thinking_lines.append(f"Issue: {result.error_message[:80]}")
                print(format_thinking(f"Candidate {i} Evaluation", "\n".join(thinking_lines)))

        # Sort by score (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def _format_fitness_report(self, result: EvaluationResult) -> str:
        """
        Format evaluation result as a fitness report for mutation prompt.

        Args:
            result: Evaluation result

        Returns:
            Formatted fitness report string
        """
        lines = []

        lines.append(f"- Syntax: {'PASS' if result.syntax_valid else 'FAIL'}")
        if not result.syntax_valid and result.error_message:
            lines.append(f"  Error: {result.error_message}")

        lines.append(f"- Runtime: {'PASS' if result.runtime_valid else 'FAIL'}")
        if not result.runtime_valid and result.error_message:
            lines.append(f"  Error: {result.error_message}")

        if result.runtime_valid:
            lines.append(f"- Correctness: {'PASS' if result.correctness_valid else 'FAIL'}")
            if not result.correctness_valid:
                if result.error_message:
                    lines.append(f"  Error: {result.error_message}")
                if result.output:
                    # Try to extract useful info from output
                    output_lines = result.output.split("\n")[:5]
                    lines.append(f"  Output: {' '.join(output_lines)}")

        return "\n".join(lines)

    async def mutate(
        self,
        candidate: CodeCandidate,
        fitness_report: str,
        verbose: Union[bool, int] = 2,
    ) -> Optional[CodeCandidate]:
        """
        Mutate a candidate based on fitness feedback.

        Args:
            candidate: Candidate to mutate
            fitness_report: Fitness report from evaluator
            verbose: Verbosity level

        Returns:
            Mutated candidate or None if mutation fails
        """
        verbose_level = normalize_verbose(verbose)

        if should_print(verbose_level, VerbosityLevel.BASIC):
            print(f"   🔄 Mutating candidate: {candidate.hypothesis}")

        prompt = PromptTemplates.mutate_candidate_prompt(
            candidate=candidate,
            fitness_report=fitness_report,
        )

        try:
            # Use CodeCandidate schema for mutation response
            response = await self.llm.structured_query(
                prompt=prompt,
                response_schema=CodeCandidate,
                system_prompt=PromptTemplates.SYSTEM_PROMPT,
                verbose=bool(verbose_level >= VerbosityLevel.BASIC),
            )

            if response:
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print(f"      ✓ Generated mutation")
                return response
            return None

        except Exception as e:
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"      ✗ Mutation failed: {e}")
            return None

    async def evolve(
        self,
        error_context: str,
        goal: str,
        original_code: str,
        test_code: Optional[str] = None,
        generations: Optional[int] = None,
        verbose: Union[bool, int] = 2,
    ) -> Optional[CodeCandidate]:
        """
        Evolve code fixes through generations.

        Args:
            error_context: Error message and code context
            goal: Goal description
            original_code: Original buggy code
            test_code: Optional test code to verify correctness
            generations: Max generations (defaults to config)
            verbose: Verbosity level

        Returns:
            Best candidate found (score 100 if perfect, otherwise best score)
        """
        generations = generations or self.max_generations
        verbose_level = normalize_verbose(verbose)

        if should_print(verbose_level, VerbosityLevel.BASIC):
            print(f"\n🧬 Starting Evolutionary Solver")
            print(f"   Population size: {self.population_size}")
            print(f"   Max generations: {generations}")

        # Generation 0: Initial population
        if should_print(verbose_level, VerbosityLevel.BASIC):
            print(f"\n--- Generation 0: Initial Population ---")

        population = await self.generate_population(
            error_context=error_context,
            goal=goal,
            n=self.population_size,
        )

        if not population:
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print("   ✗ Failed to generate initial population")
            return None

        best_candidate: Optional[CodeCandidate] = None
        best_score = -1

        # Evaluate initial population
        evaluated = await self.evaluate_candidates(
            candidates=population,
            original_code=original_code,
            test_code=test_code,
            verbose=verbose,
        )

        if evaluated:
            best_candidate, best_score = evaluated[0]
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n   Best so far: {best_candidate.hypothesis} (Score: {best_score})")

            # Perfect score - return immediately
            if best_score == 100:
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print(f"   ✅ Perfect solution found in generation 0!")
                return best_candidate

        # Evolution loop
        for gen in range(1, generations + 1):
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n--- Generation {gen} ---")

            # Select best candidate from previous generation
            if not evaluated or not best_candidate:
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print("   ⚠️  No candidates to evolve from")
                break

            # Mutate best candidate
            fitness_report = self._format_fitness_report(
                self.evaluator.evaluate(
                    code=best_candidate.code_patch,
                    test_code=test_code,
                )
            )

            mutated = await self.mutate(
                candidate=best_candidate,
                fitness_report=fitness_report,
                verbose=verbose,
            )

            # Build next generation
            next_population = []
            if mutated:
                next_population.append(mutated)

            # Generate remaining candidates to fill population
            remaining = self.population_size - len(next_population)
            if remaining > 0:
                new_candidates = await self.generate_population(
                    error_context=error_context,
                    goal=goal,
                    n=remaining,
                )
                next_population.extend(new_candidates[:remaining])

            if not next_population:
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print("   ⚠️  Failed to generate next generation")
                break

            # Evaluate new generation
            evaluated = await self.evaluate_candidates(
                candidates=next_population,
                original_code=original_code,
                test_code=test_code,
                verbose=verbose,
            )

            if evaluated:
                gen_best, gen_score = evaluated[0]
                if gen_score > best_score:
                    best_candidate = gen_best
                    best_score = gen_score
                    if should_print(verbose_level, VerbosityLevel.BASIC):
                        print(f"   🎯 New best: {gen_best.hypothesis} (Score: {gen_score})")

                # Perfect score - return immediately
                if gen_score == 100:
                    if should_print(verbose_level, VerbosityLevel.BASIC):
                        print(f"   ✅ Perfect solution found in generation {gen}!")
                    return gen_best
            else:
                if should_print(verbose_level, VerbosityLevel.BASIC):
                    print("   ⚠️  No valid candidates in this generation")
                break

        # Return best found (even if not perfect)
        if best_candidate and best_score > 0:
            if should_print(verbose_level, VerbosityLevel.BASIC):
                print(f"\n   Final best: {best_candidate.hypothesis} (Score: {best_score})")
            return best_candidate

        return None


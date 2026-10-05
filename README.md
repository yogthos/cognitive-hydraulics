# cognitive-hydraulics

A hybrid reasoning engine on [jolt](https://github.com/jolt-lang/jolt). Deliberate symbolic reasoning (System 2) with a heuristic fallback (System 1), bridged by an LLM intuition source.

The system uses a Soar-style decision cycle, the impasse taxonomy, the pressure valve, and the ACT-R utility equation. What's new is a pure, injectable core where every piece is data, the LLM is a protocol with a deterministic stub, and the load-bearing math is pinned by [writ](https://github.com/jlt-commons/writ) specs.

## The idea

One cycle: **preferences → decide → apply, or impasse**.

- Rules (pure data) state Soar preferences about operators: acceptable at a
  priority, reject, prohibit, require, best, worst, better/worse.
- `hyd.impasse/decide` reads them in Soar's order and selects one operator
  or names the impasse: `:tie`, `:conflict` (mutual better),
  `:constraint-failure` (competing requires), `:state-no-change` (nothing
  acceptable). The fifth, `:operator-no-change`, is detected on apply: an
  operator that fails or changes nothing is rejected in that state.
- An impasse pushes a substate and reads the **pressure valve** — goal-stack
  depth, time in the current state, impasses since the last progress,
  ambiguity of the proposals. Progress pops the stack and relieves it.
- Below the threshold (0.7) **System 2** deliberates: look-ahead through the
  domain's `:simulate` model turns the candidates into best/worst/reject
  preferences. Each level searched is a deeper substate, so a long search
  breaches the valve on its own. Unresolved, the next impasse nests deeper.
- At or above it **System 1** acts: the ACT-R expected gain
  `U = P·G − C − penalty + ε`, with P and C estimated by the intuition
  source and ε logistic noise from a seeded pure generator. Silent
  intuition means an indifferent pick.
- A resolution that made progress is filed as a **chunk**; `solve` recalls
  chunks (same goal, similar state) as learned best preferences, so the
  same situation never impasses twice.

## Running

    jolt -M:test             # full suite (one process per namespace)
    jolt -M:check            # writ specs: impasse, pressure, actr, memory, agent
    jolt -M:run              # blocks demo: goal-directed rules, clean solve
    jolt -M:run --naive      # no model: substates nest, then System 1 fires
    jolt -M:run --lookahead  # with a model: System 2 settles the tie

A full end-to-end example with a live LLM lives in
[examples/incident](examples/incident): an on-call triage world where the
runbook ties, DeepSeek breaks the tie, and the chunk store makes the second
incident free.

The naive demo's trace shows the valve:

    0 :subgoal - (tie, depth 1, pressure 0.38)
    1 :subgoal - (tie, depth 2, pressure 0.62)
    2 :actr :move {:b :a, :to :b} (tie, depth 3, pressure 0.85)

With nothing to deliberate with, each substate impasses again beneath the
last; pressure crosses the threshold, the intuition's estimate picks the
goal move, and the resolution is chunked. Give the agent a model
(`--lookahead`) and System 2 settles the same tie in one cycle.

## Design notes

- **Everything pure — no IO in the core.** The cycle, the valve, and the equation are pure functions over plain maps; the only IO is `hyd.persist` (chunk store as EDN), kept out of the checked namespaces. Inference is a protocol (`hyd.llm/Intuition`); the engine does no HTTP and ships no JSON or clock deps — adapters live in [examples/incident](examples/incident), which supplies two engines (DeepSeek over chat-completions, Lev over calibrated choice) against the same seam.
- **Operators are keyed by their whole map.** `{:op :move :args {:b :a :to :b}}` — moving a onto b and b onto a are different operators with different utilities.
- **Tabu counts fight loops.** An operator already applied n times is discounted n·penalty, so repetition loses to fresh options.
- **Noise replays.** ACT-R's utility noise is drawn from a Park–Miller generator threaded through the run; `:seed` in params replays a run exactly.
- **Params merge over defaults.** Pass only what you change; see `hyd.core/defaults` for the valve weights, thresholds, `:cycle-ms`, `:max-lookahead`, `:noise-s` and `:chunk-threshold`.
- **Specs first.** Every pure namespace has a [writ](https://github.com/jlt-commons/writ) spec in `test/` stating what it means: the decision procedure's preference semantics, the valve math, the utility equation, chunk recall, and the cycle's behaviour scenario by scenario.
- **The stub is first-class.** Every test and the demo run against a deterministic `StubLLM`; the real adapter is a drop-in.

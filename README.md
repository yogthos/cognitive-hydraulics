# cognitive-hydraulics

A hybrid reasoning engine on [jolt](https://github.com/jolt-lang/jolt). Deliberate symbolic reasoning (System 2) with a heuristic fallback (System 1), bridged by an LLM intuition source.

The system uses a Soar-style decision cycle, the impasse taxonomy, the pressure valve, and the ACT-R utility equation. What's new is a pure, injectable core where every piece is data, the LLM is a protocol with a deterministic stub, and the load-bearing math is pinned by [writ](https://github.com/jlt-commons/writ) specs.

## The idea

One cycle: **propose → detect impasse → act**.

- Rules (pure data) propose operators with priorities.
- No proposals is a `:no-change` impasse; a tied top is a `:tie` impasse.
- A clear winner applies. A tie at low pressure tie-breaks; every unresolved decision raises **pressure** — depth, time in state, impasse count, ambiguity — and past 0.7 the valve opens: the tied candidates go to ACT-R resolution, the utility equation `U = P·G − C − penalty + noise`, with P and C estimated by the intuition source. A heuristic pick that works is remembered as a **chunk**.

## Running

    jolt -M:test        # full suite (one process per namespace)
    jolt -M:check       # writ specs for pressure and actr
    jolt -M:run         # blocks demo: goal-directed rules, clean solve
    jolt -M:run --naive # ties escalate: tie-breaks, then System 1 fires

A full end-to-end example with a live LLM lives in
[examples/incident](examples/incident): an on-call triage world where the
runbook ties, DeepSeek breaks the tie, and the chunk store makes the second
incident free.

The naive demo's trace shows the whole story:

    0 :tie-break :move {:b :c, :to :b}
    1 :tie-break :move {:b :c, :to :table}
    2 :actr :move {:b :a, :to :b}

Two tied cycles, pressure breaches the threshold, the intuition's estimate picks the goal move, and the resolution is chunked.

## Design notes

- **Everything pure — no IO in the library.** The cycle, the valve, and the equation are pure functions over plain maps. Inference is a protocol (`hyd.llm/Intuition`); the engine does no HTTP and ships no JSON or clock deps — adapters live in [examples/incident](examples/incident), which supplies two engines (DeepSeek over chat-completions, Lev over calibrated choice) against the same seam.
- **Operators are keyed by their whole map.** `{:op :move :args {:b :a :to :b}}` — moving a onto b and b onto a are different operators with different utilities.
- **Tabu counts fight loops.** An operator already applied n times is discounted n·penalty, so repetition loses to fresh options.
- **The stub is first-class.** Every test and the demo run against a deterministic `StubLLM`; the real adapter is a drop-in.

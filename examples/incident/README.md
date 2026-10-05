# incident — cognitive-hydraulics as an on-call decision maker

A page fires on `payments`. The runbook knows every remedy — restart,
rollback, scale out — and proposes them all, tied: the rules cannot tell
which one fits, because what distinguishes them is the root cause, and only
the intuition engine can read those tea leaves (deploy freshness, what the
diff touched, the shape of the error signal).

That tie is the whole demo:

1. **Cycle 0–1** — System 2 tie-breaks (`restart`, the first candidate).
   It doesn't help; the page stays. Each tie raises the agent's depth.
2. **Pressure climbs** — 0.27, then 0.5, then ≥ 0.7: the valve opens.
3. **System 1 fires** — DeepSeek (`deepseek-chat`, JSON mode) estimates
   P(success) and cost for each remedy; ACT-R utility picks the winner.
   The pick lands (`rollback`), the page clears.
4. **Chunking** — the resolution is filed in `chunks.edn`.
5. **Run it again** — the chunk is recalled before the LLM is ever
   consulted: `llm calls: 0`.

## Run it

```fish
set -x DEEPSEEK_API_KEY ...     # already in your environment

jolt -M:run --reset    # cold: tie -> pressure -> DeepSeek -> chunk
jolt -M:run            # warm: chunk hit, zero LLM calls
jolt -M:run memory-leak   # other scenarios: memory-leak, capacity
jolt -M:run --lev --reset  # same, with lev (see below) as the intuition
jolt -M:test           # offline suite (stubbed LLM), no network
```

### lev

[jlt-commons/lev](https://github.com/jlt-commons/lev) is a second
intuition source: `--lev` swaps DeepSeek's chat call for lev's typed
`choice` question over the operators, answered with calibrated
probabilities by a local encoder (~125 ms, no API key). The operator ids
are shared with the DeepSeek adapter, so both key identically, and the
state the model sees is projected — health, deploys, the page — never the
hidden `:root-cause`. Start the server first:

```fish
cd ~/src/jlt-commons/lev && jolt -M:serve &
cd ~/src/cognitive-hydraulics/examples/incident
jolt -M:run --lev --reset
```

`LEV_URL` and `LEV_MODEL` override the endpoint (default
`http://127.0.0.1:8080`, model `english`).

## Layout

- `src/ex/incident/world.clj` — the domain: services, deploys, pages,
  operators with root-cause-dependent outcomes, the tying runbook proposer.
- `src/ex/incident/openai.clj` — the chat-completions engine: an
  OpenAI-compatible adapter (DeepSeek, llama-server, vLLM) implementing
  `hyd.llm/Intuition`, plus the shared `op-id` both engines key by.
- `src/ex/incident/deepseek.clj` — DeepSeek config + `chunk-aware`: wraps
  any `Intuition` with the chunk store so recall short-circuits the call.
- `src/ex/incident/lev.clj` — the Lev engine: a typed `choice` question
  over the same operator ids, answered with calibrated probabilities.
- `src/ex/incident/main.clj` — the shift: wires world + agent + the chosen
  engine (`--deepseek` default, `--lev`), prints the trace, persists
  `chunks.edn`.

The library itself is IO-free: HTTP and JSON are declared here, in the
example's `deps.edn`, not in the engine — the two engines are just two
implementations of the same `hyd.llm/Intuition` protocol the decision
cycle calls when pressure opens the valve.

The example has its own `deps.edn` referencing the library by
`{:local/root "../.."}`, so it exercises the engine exactly as a consumer
would.

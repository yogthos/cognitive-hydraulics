(ns hyd.llm
  "The intuition bridge.

  The library is IO-free: this protocol is its only seam to any model.
  An estimate turns operators into {operator {:p :c}} judgments; a propose
  invents operators when the rules had nothing. The deterministic StubLLM
  covers tests; real inference engines (an OpenAI-compatible HTTP adapter,
  a local decision engine) are supplied by the embedding application — see
  the library's examples/ for two.")

(defprotocol Intuition
  "The bridge to the heuristic judge."
  (estimate [this operators ctx]
    "Returns {operator {:p probability :c cost :reasoning str}} for the
    operators given the state context.")
  (propose [this ctx]
    "Operators to consider when nothing was proposed. Returns a collection
    (possibly empty)."))

(defrecord StubLLM [estimates proposals]
  Intuition
  (estimate [_ operators _]
    (select-keys estimates operators))
  (propose [_ _]
    (or proposals [])))

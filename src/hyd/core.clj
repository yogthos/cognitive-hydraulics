(ns hyd.core
  "The shared vocabulary of the engine.

  An operator is data — {:op :move, :args {...}} — and the domain knows how
  to apply it. A rule proposes operators with a priority. A result is either
  ok with the next state, or a failure with an error. Nothing here knows
  about LLMs, IO, or time."
  )

(defn proposal
  "An operator proposed by a rule at a priority."
  [op-name args priority rule]
  {:op {:op op-name :args args} :priority priority :rule rule})

(defn ok
  "A successful application: the next state and a note."
  [state note]
  {:ok true :state state :note note})

(defn fail
  "A failed application: why it failed."
  [error]
  {:ok false :error error})

(def defaults
  "The pressure valve and ACT-R constants, from the original engine."
  {:depth-threshold 3
   :time-threshold-ms 500.0
   :max-cycles 100
   :pressure-threshold 0.7
   :pressure-weights {:depth 0.35 :time 0.25 :impasse 0.20 :ambiguity 0.20}
   :impasse-scale 3.0
   :goal-value 10.0
   :noise-stddev 0.5
   :history-penalty 2.0})

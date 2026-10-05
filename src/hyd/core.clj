(ns hyd.core
  "The shared vocabulary of the engine.

  An operator is data — {:op :move, :args {...}} — and the domain knows how
  to apply it. A rule states preferences about operators: most often a
  proposal (acceptable, at a priority), sometimes a judgment (reject,
  best, better-than ...; see hyd.impasse). A result is either ok with the
  next state, or a failure with an error. Nothing here knows about LLMs,
  IO, or time.")

(defn proposal
  "An operator proposed by a rule at a priority (an acceptable preference)."
  [op-name args priority rule]
  {:op {:op op-name :args args} :priority priority :rule rule})

(defn preference
  "A unary preference about an operator: :reject :prohibit :require :best
  or :worst."
  [kind op rule]
  {:op op :pref kind :rule rule})

(defn relative
  "A binary preference: op is :better or :worse than another operator."
  [kind op than rule]
  {:op op :pref kind :than than :rule rule})

(defn ok
  "A successful application: the next state and a note."
  [state note]
  {:ok true :state state :note note})

(defn fail
  "A failed application: why it failed."
  [error]
  {:ok false :error error})

(def defaults
  "The pressure valve and ACT-R constants. Pressure weights and scales are
  the original engine's; :noise-s is ACT-R's logistic noise scale, 0.276 =
  the original Gaussian σ of 0.5 (σ = π·s/√3)."
  {:max-cycles 100
   ;; the valve
   :pressure-threshold 0.7
   :pressure-weights {:depth 0.35 :time 0.25 :impasse 0.20 :ambiguity 0.20}
   :depth-threshold 3.0
   :time-threshold-ms 500.0
   :impasse-scale 3.0
   :cycle-ms 100.0
   ;; System 2: how many levels look-ahead may search, at most
   :max-lookahead 3
   ;; System 1
   :goal-value 10.0
   :noise-s 0.276
   :history-penalty 2.0
   :seed 42
   ;; chunks: how similar a state must be for a chunk to fire
   :chunk-threshold 0.9})

(defn params
  "Caller params over the defaults; nested maps merge too, so a partial
  :pressure-weights keeps the other weights."
  [ps]
  (merge-with (fn [a b] (if (and (map? a) (map? b)) (merge a b) b))
              defaults
              ps))

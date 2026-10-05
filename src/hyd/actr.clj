(ns hyd.actr
  "ACT-R conflict resolution: the fast heuristic path.

  When deliberation stalls, the agent asks an intuition source (see
  hyd.llm) for probability-of-success and cost estimates over the
  candidate operators, and computes the classic expected gain

      U = P·G − C − history-penalty + ε

  The history penalty is tabu search: an operator already applied n times
  is discounted n·penalty, so loops lose to fresh options. ε is ACT-R's
  utility noise — logistic with scale s (:noise-s) — so resolution does not
  lock onto one choice forever. Noise is drawn from a pure Park–Miller
  generator: the caller threads the seed, and a seed replays a run.

  Operators are keyed by their whole map — {:op :move :args {...}} —
  because the arguments are the action: moving a onto b and b onto a are
  different operators with different utilities."
  (:require [hyd.llm :as llm]))

(def ^:private modulus 2147483647)

(defn next-seed
  "The Park–Miller minimal standard generator: seeds live in [1, 2³¹−2]."
  [seed]
  (mod (* 16807 seed) modulus))

(defn seed
  "Any integer as a generator seed, stirred so that nearby integers (1, 2,
  42 ...) do not start with the same near-zero draws."
  [n]
  (-> (inc (mod n (dec modulus))) next-seed next-seed next-seed))

(defn unit
  "A seed as a uniform draw in (0, 1)."
  [seed]
  (/ (double seed) modulus))

(defn logistic-noise
  "A logistic draw of scale s from a uniform u: s·ln(u / (1 − u))."
  [s u]
  (if (zero? s)
    0.0
    (* s (Math/log (/ u (- 1.0 u))))))

(defn utility
  "U = P·G − C − history-penalty, P read within [0, 1]. Deterministic; the
  noise is added by select."
  [est params history-penalty]
  (- (* (min 1.0 (max 0.0 (:p est))) (:goal-value params))
     (:c est)
     history-penalty))

(defn- usable?
  "An estimate the equation can read: numeric P and C."
  [est]
  (and (number? (:p est)) (number? (:c est))))

(defn select
  "The operator with the highest noisy utility. Estimates map operator ->
  {:p :c}; counts is operator -> times already applied (for the tabu
  penalty). An operator without a usable estimate sits out. Each scored
  operator draws one noise sample; ties go to the earliest operator.

  Returns {:chosen op :utility U-without-noise :seed next-seed}, or nil
  when nothing could be scored."
  [operators estimates counts params seed]
  (let [penalty (:history-penalty params)
        s (:noise-s params)
        scored (reduce (fn [acc op]
                         (let [est (get estimates op)]
                           (if (usable? est)
                             (let [seed' (next-seed (:seed acc))
                                   u (utility est params (* penalty (get counts op 0)))
                                   noisy (+ u (logistic-noise s (unit seed')))]
                               (assoc acc
                                      :seed seed'
                                      :best (if (or (nil? (:best acc))
                                                    (> noisy (:noisy (:best acc))))
                                              {:chosen op :utility u :noisy noisy}
                                              (:best acc))))
                             acc)))
                       {:seed seed :best nil}
                       operators)]
    (when-let [best (:best scored)]
      {:chosen (:chosen best) :utility (:utility best) :seed (:seed scored)})))

(defn resolve
  "Ask the intuition source, then select. Returns {:chosen :utility :seed
  :estimates} or nil when nothing could be estimated."
  [intuition operators ctx params seed]
  (let [estimates (into {} (llm/estimate intuition operators ctx))]
    (when-let [out (select operators estimates (or (:counts ctx) {}) params seed)]
      (assoc out :estimates estimates))))

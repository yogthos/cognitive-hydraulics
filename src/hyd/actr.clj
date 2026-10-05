(ns hyd.actr
  "ACT-R conflict resolution: the fast heuristic path.

  When deliberation stalls, the agent asks an intuition source (see
  hyd.llm) for probability-of-success and cost estimates over the tied
  operators, and computes the classic utility

      U = P·G − C − history-penalty + noise

  The history penalty is tabu search: an operator already applied n times is
  discounted n·penalty, so loops lose to fresh options. Noise keeps
  resolution from locking onto one choice forever.

  Operators are keyed by their whole map — {:op :move :args {...}} — because
  the arguments are the action: moving a onto b and b onto a are different
  operators with different utilities."
  (:require [hyd.llm :as llm]))

(defn utility
  "U = P·G − C − history-penalty. Deterministic; noise is deliberately the
  caller's affair so tests pin the math."
  [{:keys [p c]} {:keys [goal-value]} history-penalty]
  (- (* p goal-value) c history-penalty))

(defn select
  "The operator with the highest utility. Estimates map operator -> {:p :c};
  counts is operator -> times already applied (for the tabu penalty). An
  operator without an estimate sits out. Ties go to the earliest operator
  in the list."
  [operators estimates counts {:keys [history-penalty] :or {history-penalty 2.0} :as params}]
  (let [scored (for [op operators
                     :let [est (get estimates op)]
                     :when est]
                 {:op op
                  :u (utility est params (* history-penalty (get counts op 0)))
                  :est est})]
    (when (seq scored)
      (:op (first (sort-by (fn [{u :u}] (- u)) scored))))))

(defn resolve
  "Ask the intuition source, then select. Returns {:chosen op :estimates m}
  or nil when nothing could be estimated."
  [intuition operators ctx params]
  (let [estimates (into {} (seq (llm/estimate intuition operators ctx)))
        counts (or (:counts ctx) {})]
    (when-let [chosen (select operators estimates counts params)]
      {:chosen chosen :estimates estimates})))

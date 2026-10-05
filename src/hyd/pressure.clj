(ns hyd.pressure
  "The pressure valve. Cognitive load is a single number: how deep the goal
  stack, how long stuck in one state, how many impasses, how undecided the
  operators. Above the threshold the agent stops deliberating (System 2)
  and acts on heuristics (System 1)."
  (:require [hyd.core :as core]))

(def ^:private weights
  "Contribution of each component to the total, from the original engine."
  (:pressure-weights core/defaults))

(defn- num-or-zero
  "A metric value that may be missing or nonsense reads as zero load."
  [x]
  (if (number? x) x 0))

(defn- saturate
  "A ratio clipped to [0, 1]."
  [x limit]
  (let [x (num-or-zero x)]
    (cond (neg? x) 0.0
          (>= x limit) 1.0
          :else (double (/ x limit)))))

(defn pressure
  "Cognitive pressure in [0, 1]: the weighted sum of the saturated
  components. Metrics: {:depth n, :time-ms n, :impasses n, :ambiguity f};
  missing or non-numeric keys read as zero."
  [{:keys [depth time-ms impasses ambiguity] :or {depth 0 time-ms 0 impasses 0 ambiguity 0.0}}]
  (let [depth-pressure (saturate depth (:depth-threshold core/defaults))
        time-pressure (saturate time-ms (:time-threshold-ms core/defaults))
        impasse-pressure (saturate impasses (:impasse-scale core/defaults))]
    (min 1.0
         (+ (* (:depth weights) depth-pressure)
            (* (:time weights) time-pressure)
            (* (:impasse weights) impasse-pressure)
            (* (:ambiguity weights) (min 1.0 (max 0.0 (num-or-zero ambiguity))))))))

(defn fallback?
  "True when pressure is at or above the act-now threshold."
  [metrics]
  (>= (pressure metrics) (:pressure-threshold core/defaults)))

(defn level
  "A name for the pressure band: :calm :elevated :high :critical."
  [p]
  (cond (< p 0.3) :calm
        (< p 0.5) :elevated
        (< p 0.7) :high
        :else :critical))

(ns hyd.pressure
  "The pressure valve. Cognitive load is a single number: how deep the goal
  stack, how long stuck in one state, how many impasses since the last
  progress, how undecided the operators. Above the threshold the agent
  stops deliberating (System 2) and acts on heuristics (System 1).

  Weights, scales and the threshold are params (see hyd.core/defaults).")

(defn- saturate
  "A load as a share of its scale, at most 1."
  [x limit]
  (min 1.0 (/ (double x) limit)))

(defn pressure
  "Cognitive pressure in [0, 1]: the weighted sum of the saturated
  components. Metrics: {:depth n, :time-ms n, :impasses n, :ambiguity f},
  all non-negative, ambiguity in [0, 1]."
  [metrics params]
  (let [w (:pressure-weights params)]
    (min 1.0
         (+ (* (:depth w) (saturate (:depth metrics) (:depth-threshold params)))
            (* (:time w) (saturate (:time-ms metrics) (:time-threshold-ms params)))
            (* (:impasse w) (saturate (:impasses metrics) (:impasse-scale params)))
            (* (:ambiguity w) (:ambiguity metrics))))))

(defn fallback?
  "True when pressure is at or above the act-now threshold."
  [metrics params]
  (>= (pressure metrics params) (:pressure-threshold params)))

(defn level
  "A name for the pressure band: :calm :elevated :high, and :critical at
  or above the act-now threshold."
  [p params]
  (cond (>= p (:pressure-threshold params)) :critical
        (< p 0.3) :calm
        (< p 0.5) :elevated
        :else :high))

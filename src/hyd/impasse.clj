(ns hyd.impasse
  "Impasse detection for the decision cycle.

  An impasse is what the symbolic layer cannot settle on its own: no rule
  fired (:no-change), or the top proposals are tied (:tie). The detector is
  pure — it reads the proposal list and says what kind of impasse, if any,
  with the tied candidates attached."
  (:require [hyd.core :as core]))

(defn ambiguity
  "How undecided the proposals are, 0 (a clear winner) to 1 (all equal or
  none). Contenders are proposals within 10% of the priority range below the
  top; the score is the share of the field they make up."
  [proposals]
  (cond
    (empty? proposals) 1.0
    (= 1 (count proposals)) 0.0
    :else (let [priorities (map :priority proposals)
                mx (apply max priorities)
                mn (apply min priorities)]
            (if (= mx mn)
              1.0
              (let [cutoff (- mx (* 0.1 (- mx mn)))
                    contenders (count (filter #(>= % cutoff) priorities))]
                (/ (double (dec contenders)) (count proposals)))))))

(defn detect
  "Classify the proposal list: nil when a rule won outright, otherwise
  {:type :no-change} or {:type :tie :candidates [...]}."
  [proposals]
  (cond
    (empty? proposals) {:type :no-change}
    (= 1 (count proposals)) nil
    :else (let [mx (apply max (map :priority proposals))
                top (filter #(= mx (:priority %)) proposals)]
            (when (> (count top) 1)
              {:type :tie :candidates top}))))

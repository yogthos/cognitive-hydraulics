(ns hyd.pressure-spec
  "The contract for hyd.pressure: the valve math.

  Pressure is a weighted sum of saturated load components in [0,1]. The
  laws pin the number itself (the weights), its bounds, and the bands."
  (:require [writ.spec :refer [spec ann law refine graph]]))

(spec hyd.pressure)

;; the meaningful metric components
(refine NonNegDouble [x Double] (and (<= 0.0 x) (<= x 1.0)))
(refine LoadDouble [x Double] (and (<= 0.0 x)))

(ann pressure [(Map Keyword Any) -> Double])
(ann fallback? [(Map Keyword Any) -> Bool])
(ann level [Double -> Keyword])

;; metrics go in, a pressure in [0,1] comes out; past that the valve reads
;; it as critical
(graph valve
  {:states {:metrics (Map Keyword Any), :calm NonNegDouble, :critical NonNegDouble}
   :edges  {:metrics {[pressure] #{:calm}}}})

;; the weights: full load on one component is that component's weight
(law depth-weight
  (= (pressure {:depth 3 :time-ms 0.0 :impasses 0 :ambiguity 0.0}) 0.35))
(law time-weight
  (= (pressure {:depth 0 :time-ms 500.0 :impasses 0 :ambiguity 0.0}) 0.25))
(law impasse-weight
  (= (pressure {:depth 0 :time-ms 0.0 :impasses 3 :ambiguity 0.0}) 0.2))
(law ambiguity-weight
  (= (pressure {:depth 0 :time-ms 0.0 :impasses 0 :ambiguity 1.0}) 0.2))

;; saturation: past the threshold a component adds nothing, and the
;; saturated value is the weight
(law depth-saturates
  (= (pressure {:depth 30 :time-ms 0.0 :impasses 0 :ambiguity 0.0}) 0.35))
(law time-saturates
  (= (pressure {:depth 0 :time-ms 5000.0 :impasses 0 :ambiguity 0.0}) 0.25))
(law impasse-saturates
  (= (pressure {:depth 0 :time-ms 0.0 :impasses 300 :ambiguity 0.0}) 0.2))

;; zero load is zero pressure; full load is one
(law zero-at-zero
  (= (pressure {:depth 0 :time-ms 0.0 :impasses 0 :ambiguity 0.0}) 0.0))
(law full-load
  (= (pressure {:depth 3 :time-ms 500.0 :impasses 3 :ambiguity 1.0}) 1.0))

;; every pressure below the threshold of each band names that band
(law level-partitions
  (forall [p NonNegDouble]
    (= (level p)
       (cond (< p 0.3) :calm
             (< p 0.5) :elevated
             (< p 0.7) :high
             :else :critical))))

;; fallback fires at or above the threshold
(law fallback-at-threshold
  (forall [d Nat, t LoadDouble, i Nat, a NonNegDouble]
    (=> (>= (pressure {:depth d :time-ms t :impasses i :ambiguity a}) 0.7)
        (fallback? {:depth d :time-ms t :impasses i :ambiguity a}))))
(law no-fallback-below
  (= (fallback? {:depth 0 :time-ms 0.0 :impasses 0 :ambiguity 0.0}) false))

;; pressure lives in [0,1]
(law bounded
  (forall [d Nat, t LoadDouble, i Nat, a NonNegDouble]
    (let [p (pressure {:depth d :time-ms t :impasses i :ambiguity a})]
      (and (<= 0.0 p) (<= p 1.0)))))

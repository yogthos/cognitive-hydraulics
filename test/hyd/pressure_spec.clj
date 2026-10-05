(ns hyd.pressure-spec
  "The contract for hyd.pressure: the valve math.

  Pressure is a weighted sum of load components, each saturated into
  [0,1] against its scale, capped at 1. The weights, scales and the act-now
  threshold are the caller's params — the defaults are the original
  engine's. The laws pin the number (the weights), its bounds, its
  monotonicity, the threshold and the bands."
  (:require [writ.spec :refer [spec ann law refine graph example]]))

(spec hyd.pressure)

;; --- vocabulary -------------------------------------------------------------

(refine Unit [x Double] (and (<= 0.0 x) (<= x 1.0)))
(refine Load [x Double] (<= 0.0 x))
(refine Scale [x Double] (< 0.0 x))

(refine Metrics [m {:depth Nat, :time-ms Load, :impasses Nat, :ambiguity Unit}] true)

(refine Params [p {:pressure-weights {:depth Unit, :time Unit, :impasse Unit, :ambiguity Unit}
                  :depth-threshold Scale
                  :time-threshold-ms Scale
                  :impasse-scale Scale
                  :pressure-threshold Unit}]
  true)

(def D
  "The original engine's constants (hyd.core/defaults, restated)."
  {:pressure-weights {:depth 0.35 :time 0.25 :impasse 0.20 :ambiguity 0.20}
   :depth-threshold 3.0
   :time-threshold-ms 500.0
   :impasse-scale 3.0
   :pressure-threshold 0.7})

(defn sat [x limit] (min 1.0 (/ (double x) limit)))

(defn model
  "Pressure as the problem states it."
  [m p]
  (let [w (:pressure-weights p)]
    (min 1.0 (+ (* (:depth w) (sat (:depth m) (:depth-threshold p)))
                (* (:time w) (sat (:time-ms m) (:time-threshold-ms p)))
                (* (:impasse w) (sat (:impasses m) (:impasse-scale p)))
                (* (:ambiguity w) (:ambiguity m))))))

(defn close? [a b] (< (abs (- a b)) 1.0e-9))

(refine Calm [x Unit] (< x 0.3))
(refine Critical [x Unit] (<= 0.7 x))

;; --- signatures --------------------------------------------------------------

(ann pressure [Metrics Params -> Double])
(ann fallback? [Metrics Params -> Bool])
(ann level [Double Params -> Keyword])

;; metrics go in, a pressure in [0,1] comes out
(graph valve
  {:states {:metrics Metrics, :pressure Unit}
   :edges  {:metrics {[pressure Params] #{:pressure}}}})

;; --- the number --------------------------------------------------------------

(law agrees-with-model
  (forall [m Metrics, p Params]
    (close? (pressure m p) (model m p))))

;; the weights: full load on one component is that component's weight
(law depth-weight (= (pressure {:depth 3 :time-ms 0.0 :impasses 0 :ambiguity 0.0} D) 0.35))
(law time-weight (= (pressure {:depth 0 :time-ms 500.0 :impasses 0 :ambiguity 0.0} D) 0.25))
(law impasse-weight (= (pressure {:depth 0 :time-ms 0.0 :impasses 3 :ambiguity 0.0} D) 0.2))
(law ambiguity-weight (= (pressure {:depth 0 :time-ms 0.0 :impasses 0 :ambiguity 1.0} D) 0.2))

;; saturation: past its scale a component adds nothing more
(law depth-saturates
  (forall [d Nat]
    (= (pressure {:depth (+ 3 d) :time-ms 0.0 :impasses 0 :ambiguity 0.0} D) 0.35)))

;; zero load is zero pressure, whatever the weights; full load is one
(law zero-at-zero
  (forall [p Params]
    (= 0.0 (pressure {:depth 0 :time-ms 0.0 :impasses 0 :ambiguity 0.0} p))))
(law full-load (= (pressure {:depth 3 :time-ms 500.0 :impasses 3 :ambiguity 1.0} D) 1.0))

;; the caller's weights are the weights
(law weights-are-params
  (forall [w Unit]
    (close? w (pressure {:depth 3 :time-ms 0.0 :impasses 0 :ambiguity 0.0}
                        (assoc-in D [:pressure-weights :depth] w)))))

;; more load never lowers pressure
(law monotone
  (forall [m Metrics, p Params, k Nat]
    (and (<= (pressure m p) (pressure (update m :depth + k) p))
         (<= (pressure m p) (pressure (update m :impasses + k) p))
         (<= (pressure m p) (pressure (update m :time-ms + k) p)))))

;; --- the valve ---------------------------------------------------------------

;; fallback fires exactly at or above the caller's threshold
(law fallback-is-threshold
  (forall [m Metrics, p Params]
    (= (fallback? m p) (>= (pressure m p) (:pressure-threshold p)))))

(law threshold-is-params
  (let [m {:depth 2 :time-ms 0.0 :impasses 2 :ambiguity 1.0}]   ; 0.2333 + 0.1333 + 0.2
    (and (fallback? m (assoc D :pressure-threshold 0.5))
         (not (fallback? m D)))))

;; --- the bands ---------------------------------------------------------------

;; critical is exactly the valve's range; below it, fixed bands
(law level-partitions
  (forall [x Unit, p Params]
    (= (level x p)
       (cond (>= x (:pressure-threshold p)) :critical
             (< x 0.3) :calm
             (< x 0.5) :elevated
             :else :high))))

(example level [0.0 D] :calm)
(example level [0.69 D] :high)
(example level [0.7 D] :critical)

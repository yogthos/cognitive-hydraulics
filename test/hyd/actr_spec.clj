(ns hyd.actr-spec
  "The contract for hyd.actr: conflict resolution by expected gain.

  U = P·G − C − penalty + ε. P and C come from the intuition source, G is
  the goal's value, the penalty is tabu (times already applied × the
  history penalty), and ε is ACT-R's utility noise: logistic with scale s,
  drawn from a pure Park–Miller generator so a seed replays a run.

  Estimates that are not numbers sit out; P is clamped into [0, 1]."
  (:require [writ.spec :refer [spec ann law refine graph example assume]]))

(spec hyd.actr)

(assume Math/log [Double -> Double])

;; --- vocabulary -------------------------------------------------------------

(def M 2147483647)

(refine Prob [p Double] (and (<= 0.0 p) (<= p 1.0)))
(refine NonNeg [x Double] (<= 0.0 x))
(refine Seed [n Int] (and (<= 1 n) (< n M)))
(refine Open [u Double] (and (< 0.0 u) (< u 1.0)))
(refine Estimate [e {:p Prob, :c NonNeg}] true)
;; what an intuition source may actually say
(refine RawEstimate [e {:p Double, :c Double}] true)

(def P0 {:goal-value 10.0 :noise-s 0.0 :history-penalty 2.0})

(defn gain [e params penalty]
  (- (* (min 1.0 (max 0.0 (:p e))) (:goal-value params)) (:c e) penalty))

(defn argmax-first
  "The earliest operator of the highest noiseless utility."
  [ops ests counts params]
  (let [scored (filter (fn [o] (get ests o)) ops)
        u (fn [o] (gain (get ests o) params (* (:history-penalty params) (get counts o 0))))]
    (when (seq scored)
      (reduce (fn [best o] (if (> (u o) (u best)) o best)) scored))))

;; --- signatures --------------------------------------------------------------

(ann utility [RawEstimate (Map Keyword Any) Double -> Double])
(ann seed [Int -> Seed])
(ann next-seed [Seed -> Seed])
(ann unit [Seed -> Open])
(ann logistic-noise [NonNeg Open -> Double])
(ann select [(List Keyword) (Map Keyword Any) (Map Keyword Nat) (Map Keyword Any) Seed
             -> (Opt {:chosen Keyword, :utility Double, :seed Seed})])
(ann resolve [Any (List Keyword) (Map Keyword Any) (Map Keyword Any) Seed
              -> (Opt {:chosen Keyword, :utility Double, :seed Seed, :estimates (Map Any Any)})])

;; candidates and estimates go in, a choice comes out
(graph resolution
  {:states {:candidates (List Keyword), :decided (Opt {:chosen Keyword, :utility Double, :seed Seed})}
   :edges  {:candidates {[select (Map Keyword Any) (Map Keyword Nat) (Map Keyword Any) Seed]
                         #{:decided}}}})

;; --- the equation ------------------------------------------------------------

(law equation (= (utility {:p 0.9 :c 1.0} {:goal-value 10.0} 2.0) 6.0))
(law equation-zero-cost (= (utility {:p 0.5 :c 0.0} {:goal-value 10.0} 0.0) 5.0))
(law equation-goal-scales (= (utility {:p 0.5 :c 0.0} {:goal-value 20.0} 0.0) 10.0))

(law penalty-subtracts
  (forall [h NonNeg]
    (= (utility {:p 0.9 :c 1.0} {:goal-value 10.0} h) (- 8.0 h))))

(law equation-model
  (forall [e Estimate, g NonNeg, h NonNeg]
    (= (utility e {:goal-value g} h) (gain e {:goal-value g} h))))

;; --- the noise source --------------------------------------------------------

(law park-miller (forall [s Seed] (= (next-seed s) (mod (* 16807 s) M))))
(example next-seed [1] 16807)
;; any integer seeds the generator, and nearby integers seed it far apart
(law seed-in-range (forall [n Int] (Seed? (seed n))))
(law seed-is-stirred
  (forall [n Seed]
    (= (seed (dec n)) (next-seed (next-seed (next-seed n))))))
(law seed-mixes
  (< 1000000 (abs (- (seed 1) (seed 2)))))

(law unit-scales (forall [s Seed] (= (unit s) (/ (double s) M))))

(law noise-centred (forall [s NonNeg] (= 0.0 (logistic-noise s 0.5))))
(law noise-silent-at-zero-scale (forall [u Open] (= 0.0 (logistic-noise 0.0 u))))
;; over the draws the generator makes
(law noise-antisymmetric
  (forall [s NonNeg, k Seed]
    (let [u (unit k)]
      (< (abs (+ (logistic-noise s u) (logistic-noise s (- 1.0 u))))
         (* 1.0e-6 (+ 1.0 (abs (logistic-noise s u))))))))
(law noise-rises
  (forall [s NonNeg, u Open, v Open]
    (=> (and (pos? s) (< u v)) (< (logistic-noise s u) (logistic-noise s v)))))

;; --- selection ---------------------------------------------------------------

;; without noise, selection is argmax, earliest first on ties
(law select-is-argmax
  (forall [ops (List Keyword), ests (Map Keyword Estimate), counts (Map Keyword Nat), seed Seed]
    (= (:chosen (select ops ests counts P0 seed))
       (argmax-first ops ests counts P0))))

(law select-picks-max
  (forall [pa Prob, c NonNeg, seed Seed]
    (=> (< pa 1.0)
        (= :a (:chosen (select [:a :b] {:a {:p 1.0 :c c} :b {:p pa :c c}} {} P0 seed))))))

(law select-ties-go-first
  (forall [seed Seed]
    (= :b (:chosen (select [:b :a] {:a {:p 0.5 :c 1.0} :b {:p 0.5 :c 1.0}} {} P0 seed)))))

(law select-empty-estimates (= nil (select [:a] {} {} P0 1)))

;; the tabu penalty: a used operator loses to a fresh equal one
(law select-tabu-loses
  (= :b (:chosen (select [:a :b] {:a {:p 0.9 :c 1.0} :b {:p 0.9 :c 1.0}} {:a 2} P0 1))))

;; an estimate that is not numbers sits out
(law garbage-sits-out
  (forall [seed Seed]
    (let [b {:p 0.1 :c 5.0}]
      (and (= :b (:chosen (select [:a :b] {:a {:p "high" :c 1.0} :b b} {} P0 seed)))
           (= :b (:chosen (select [:a :b] {:a {:p 0.9 :c nil} :b b} {} P0 seed)))
           (= :b (:chosen (select [:a :b] {:a 0.9 :b b} {} P0 seed)))))))

;; P past [0,1] is read at the boundary
(law p-is-clamped
  (and (= 10.0 (:utility (select [:a] {:a {:p 3.0 :c 0.0}} {} P0 1)))
       (= 0.0 (:utility (select [:a] {:a {:p -1.0 :c 0.0}} {} P0 1)))))

;; the reported utility is the chosen operator's
(law reports-utility
  (forall [e Estimate, seed Seed]
    (= (gain e P0 0.0) (:utility (select [:a] {:a e} {} P0 seed)))))

;; noise: close calls go either way across seeds, and a seed replays
(law noise-moves-close-calls
  (let [ests {:a {:p 0.50 :c 0.0} :b {:p 0.49 :c 0.0}}
        params (assoc P0 :noise-s 1.0)]
    (= #{:a :b} (set (map (fn [s] (:chosen (select [:a :b] ests {} params s))) (map seed (range 1 60)))))))

(law seed-replays
  (forall [seed Seed]
    (let [ests {:a {:p 0.50 :c 0.0} :b {:p 0.49 :c 0.0}}
          params (assoc P0 :noise-s 1.0)]
      (= (select [:a :b] ests {} params seed) (select [:a :b] ests {} params seed)))))

;; the seed advances once per operator drawn for
(law seed-advances
  (forall [seed Seed]
    (= (next-seed (next-seed seed))
       (:seed (select [:a :b] {:a {:p 0.5 :c 0.0} :b {:p 0.4 :c 0.0}} {} P0 seed)))))

;; --- resolve -----------------------------------------------------------------

;; resolve is select over what the intuition said
(law resolve-is-select-over-estimates
  (forall [ests (Map Keyword Estimate), seed Seed]
    (let [stub (hyd.llm/->StubLLM ests nil)
          ops (keys ests)]
      (= (select ops ests {} P0 seed)
         (when-let [r (resolve stub ops {} P0 seed)] (dissoc r :estimates))))))

(law resolve-chooses
  (let [stub (hyd.llm/->StubLLM {:a {:p 0.9 :c 1.0} :b {:p 0.2 :c 1.0}} nil)
        out (resolve stub [:a :b] {} P0 1)]
    (and (= :a (:chosen out))
         (= {:p 0.9 :c 1.0} (get-in out [:estimates :a])))))

(law resolve-nothing-estimated
  (= nil (resolve (hyd.llm/->StubLLM {} nil) [:a :b] {} P0 1)))

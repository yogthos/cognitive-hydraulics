(ns hyd.actr-spec
  "The contract for hyd.actr's utility math and selection.

  U = P·G − C − penalty: the equation itself is pinned by point laws, the
  selection by argmax and tabu laws."
  (:require [writ.spec :refer [spec ann law refine graph]]))

(spec hyd.actr)

(refine Prob [p Double] (and (<= 0.0 p) (<= p 1.0)))
(refine NonNeg [x Double] (<= 0.0 x))

(ann utility [(Map Keyword Any) (Map Keyword Any) Double -> Double])
(ann select [(List Any) (Map Any Any) (Map Any Any) (Map Keyword Any) -> Any])
(ann resolve [Any (List Any) (Map Any Any) (Map Keyword Any) -> Any])

;; candidates go in, a choice comes out
(graph resolution
  {:states {:candidates (List Any), :decided Any}
   :edges  {:candidates {[select (Map Any Any) (Map Any Any) (Map Keyword Any)]
                          #{:decided}}}})

;; the equation itself, on particular values
(law equation
  (= (utility {:p 0.9 :c 1.0} {:goal-value 10.0} 2.0) 6.0))
(law equation-zero-cost
  (= (utility {:p 0.5 :c 0.0} {:goal-value 10.0} 0.0) 5.0))
(law equation-goal-scales
  (= (utility {:p 0.5 :c 0.0} {:goal-value 20.0} 0.0) 10.0))

;; and the shape in between: every additional unit of penalty subtracts one
(law penalty-subtracts
  (forall [h NonNeg]
    (= (utility {:p 0.9 :c 1.0} {:goal-value 10.0} h) (- 8.0 h))))

;; selection is argmax
(law select-picks-max
  (forall [pa Prob, c NonNeg, g NonNeg]
    (=> (< pa 1.0)
        (let [a {:op :a :args {}}
              b {:op :b :args {}}]
          (= a (select [a b] {a {:p 1.0 :c c} b {:p pa :c c}} {}
                       {:goal-value g :noise-stddev 0.0 :history-penalty 2.0}))))))
(law select-empty-estimates
  (= (select [{:op :a :args {}}] {} {} {:goal-value 1.0 :noise-stddev 0.0}) nil))

;; the tabu penalty: a used operator loses to a fresh equal one
(law select-tabu-loses
  (let [a {:op :a :args {}}
        b {:op :b :args {}}]
    (= b (select [a b] {a {:p 0.9 :c 1.0} b {:p 0.9 :c 1.0}}
                 {a 2}
                 {:goal-value 10.0 :noise-stddev 0.0 :history-penalty 2.0}))))

;; resolve hands the intuition's estimates to select
(law resolve-chooses
  (let [a {:op :a :args {}}
        stub (hyd.llm/->StubLLM {a {:p 0.9 :c 1.0}} nil)]
    (= a (:chosen (resolve stub [a] {} {:goal-value 10.0 :noise-stddev 0.0})))))

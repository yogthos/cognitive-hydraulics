(ns hyd.agent-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.actr :as actr]
            [hyd.llm :as llm]
            [hyd.agent :as agent]
            [hyd.blocks :as blocks]))

(def base
  {:state {:on {:a :table :b :table}}
   :goal {:target {:a :b}}
   :apply blocks/apply-op
   :goal-met? blocks/goal-met?
   :intuition (llm/->StubLLM {} nil)
   :params {:goal-value 10.0 :noise-stddev 0.0 :history-penalty 2.0}})

(def a-on-b {:op :move :args {:b :a :to :b}})

(deftest solves-by-rules-alone
  (testing "a clear rule path reaches the goal without the LLM"
    (let [out (agent/solve (assoc base :proposer agent/goal-directed-proposer))]
      (is (:solved? out))
      (is (= {:on {:a :b :b :table}} (:final-state out)))
      (is (empty? (:chunks out)))
      (is (= [:rule] (distinct (map :via (:trace out))))))))

(deftest oscillation-escalates-to-system-one
  (testing "naive ties oscillate, pressure climbs, ACT-R takes over"
    (let [smart-stub (llm/->StubLLM {a-on-b {:p 0.9 :c 1.0 :reasoning "a onto b"}} nil)
          out (agent/solve (assoc base
                                  :proposer agent/blocks-proposer
                                  :intuition smart-stub))]
      (is (:solved? out))
      (is (= {:on {:a :b :b :table}} (:final-state out)))
      (is (some #(= :tie-break (:via %)) (:trace out)))
      (is (some #(= :actr (:via %)) (:trace out)))
      (is (= 1 (count (:chunks out)))))))

(deftest no-change-asks-intuition-to-propose
  (testing "when no rule fires, the LLM generates the operator"
    (let [stub (llm/->StubLLM {a-on-b {:p 0.9 :c 1.0 :reasoning "goal move"}} [a-on-b])
          out (agent/solve (assoc base
                                  :proposer (constantly [])
                                  :intuition stub))]
      (is (:solved? out))
      (is (some #(= :actr-generate (:via %)) (:trace out))))))

(deftest cycle-bound-terminates
  (testing "a dumb intuition and a naive proposer still terminate at the bound"
    (let [out (agent/solve (assoc base
                                  :proposer agent/blocks-proposer
                                  :max-cycles 20))]
      (is (not (:solved? out)))
      (is (<= (:cycles out) 20)))))

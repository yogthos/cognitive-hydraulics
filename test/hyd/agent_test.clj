(ns hyd.agent-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.agent :as agent]
            [hyd.blocks :as blocks]
            [hyd.core :as core]
            [hyd.llm :as llm]))

(def base
  {:state {:on {:a :table :b :table}}
   :goal {:target {:a :b}}
   :apply blocks/apply-op
   :goal-met? blocks/goal-met?
   :intuition (llm/->StubLLM {} nil)
   :params {:noise-s 0.0}})

(def a-on-b {:op :move :args {:b :a :to :b}})

(defn- vias [out] (mapv :via (:trace out)))

(deftest solves-by-rules-alone
  (testing "a clear rule path reaches the goal without the LLM"
    (let [out (agent/solve (assoc base :proposer blocks/goal-directed-proposer))]
      (is (:solved? out))
      (is (= {:on {:a :b :b :table}} (:final-state out)))
      (is (empty? (:chunks out)))
      (is (= [:rule] (vias out))))))

(deftest clear-winner-wherever-listed
  (testing "the highest priority is applied even when listed last"
    (let [out (agent/solve (assoc base :proposer
                                  (fn [_ _] [(core/proposal :move {:b :b :to :a} 1.0 "low")
                                             (core/proposal :move {:b :a :to :b} 5.0 "high")])))]
      (is (:solved? out))
      (is (= [a-on-b] (keep :op (:trace out)))))))

(deftest substates-escalate-to-system-one
  (testing "without a model, ties nest substates until the valve opens"
    (let [out (agent/solve (assoc base
                                  :proposer blocks/naive-proposer
                                  :intuition (llm/->StubLLM {a-on-b {:p 0.9 :c 1.0}} nil)))]
      (is (:solved? out))
      (is (= [:subgoal :subgoal :actr] (vias out)))
      (is (= [1 2 3] (mapv :depth (:trace out))))
      (is (= 1 (count (:chunks out)))))))

(deftest lookahead-deliberates
  (testing "with a model, System 2 resolves the tie by look-ahead"
    (let [out (agent/solve (assoc base :proposer blocks/naive-proposer :simulate blocks/apply-op))]
      (is (:solved? out))
      (is (= [:lookahead] (vias out))))))

(deftest operator-no-change
  (testing "a failing operator is rejected in its state, not retried forever"
    (let [bad {:op :move :args {:b :a :to :zz}}
          out (agent/solve (assoc base
                                  :proposer (fn [_ _] [(core/proposal :move {:b :a :to :zz} 1.0 "bad")])
                                  :max-cycles 10))]
      (is (not (:solved? out)))
      (is (= 1 (count (filter #{bad} (keep :op (:trace out))))))
      (is (= :operator-no-change (:impasse (first (:trace out))))))))

(deftest no-change-asks-intuition-to-propose
  (testing "when no rule fires, the LLM generates the operator"
    (let [stub (llm/->StubLLM {a-on-b {:p 0.9 :c 1.0 :reasoning "goal move"}} [a-on-b])
          out (agent/solve (assoc base :proposer (constantly []) :intuition stub))]
      (is (:solved? out))
      (is (some #(= :actr-generate (:via %)) (:trace out))))))

(deftest chunks-fire-next-time
  (testing "a learned resolution fires as a preference on the next run"
    (let [first-run (agent/solve (assoc base
                                        :proposer blocks/naive-proposer
                                        :intuition (llm/->StubLLM {a-on-b {:p 0.9 :c 1.0}} nil)))
          again (agent/solve (assoc base :proposer blocks/naive-proposer
                                    :store (:store first-run)))]
      (is (= [:chunk] (vias again))))))

(deftest cycle-bound-terminates
  (testing "a silent intuition and a naive proposer still terminate at the bound"
    (let [out (agent/solve (assoc base :proposer (constantly []) :max-cycles 20))]
      (is (not (:solved? out)))
      (is (= 20 (:cycles out))))))

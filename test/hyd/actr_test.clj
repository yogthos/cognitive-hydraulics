(ns hyd.actr-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.actr :as actr]
            [hyd.core :as core]
            [hyd.memory :as memory]
            [hyd.llm :as llm]))

(def a->b {:op :move :args {:b :a :to :b}})
(def b->a {:op :move :args {:b :b :to :a}})

(deftest utility-equation
  (testing "U = P·G − C − penalty, without noise"
    (is (= 8.0 (actr/utility {:p 0.9 :c 1.0} {:goal-value 10.0 :noise-stddev 0.0} 0)))
    (is (= -1.0 (actr/utility {:p 0.9 :c 10.0} {:goal-value 10.0 :noise-stddev 0.0} 0))))
  (testing "history penalty subtracts linearly"
    ;; utility takes the penalty to subtract: 0.9·10 − 1 − 2 = 6.0
    (is (= 6.0 (actr/utility {:p 0.9 :c 1.0} {:goal-value 10.0 :noise-stddev 0.0} 2)))))

(deftest tabu-counts-keyed-by-operator
  (testing "counts from memory/record feed the tabu penalty"
    (let [rst {:op :restart :args {:service "payments"}}
          sc {:op :scale-out :args {:service "payments"}}
          est {rst {:p 0.9 :c 1.0} sc {:p 0.4 :c 1.0}}
          wm (-> (memory/wm {})
                 (memory/record {:op rst :priority 1 :rule "r"} (core/ok {} "") {})
                 (memory/record {:op rst :priority 1 :rule "r"} (core/ok {} "") {})
                 (memory/record {:op rst :priority 1 :rule "r"} (core/ok {} "") {}))]
      (is (= 3 (get (:counts wm) rst)))
      (is (= :scale-out (:op (actr/select [rst sc] est (:counts wm)
                                          {:history-penalty 2.0 :goal-value 10.0})))))))

(deftest selection
  (let [params {:goal-value 10.0 :noise-stddev 0.0 :history-penalty 2.0}
        estimates {a->b {:p 0.9 :c 1.0}
                   b->a {:p 0.2 :c 9.0}}]
    (testing "higher utility wins"
      (is (= a->b (actr/select [a->b b->a] estimates {} params))))
    (testing "tabu counts can flip the choice"
      (is (= b->a (actr/select [a->b b->a]
                               (assoc estimates a->b {:p 0.1 :c 1.0})
                               {a->b 5}
                               params))))
    (testing "operators without estimates sit out"
      (is (= b->a (actr/select [a->b b->a] {b->a {:p 0.5 :c 2.0}} {} params))))))

(deftest resolution-with-stub
  (testing "resolve picks the highest-utility candidate from estimates"
    (let [llm (llm/->StubLLM {a->b {:p 0.9 :c 1.0 :reasoning "clear win"}
                              b->a {:p 0.3 :c 8.0 :reasoning "long shot"}} nil)
          out (actr/resolve llm [a->b b->a] {} {:goal-value 10.0 :noise-stddev 0.0})]
      (is (= a->b (:chosen out)))
      (is (= "clear win" (get-in out [:estimates a->b :reasoning])))))
  (testing "propose returns the stubbed operators for no-change impasses"
    (let [llm (llm/->StubLLM {} [a->b])]
      (is (= [a->b] (llm/propose llm {}))))))

(ns hyd.actr-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.actr :as actr]
            [hyd.core :as core]
            [hyd.memory :as memory]
            [hyd.llm :as llm]))

(def a->b {:op :move :args {:b :a :to :b}})
(def b->a {:op :move :args {:b :b :to :a}})
(def quiet {:goal-value 10.0 :noise-s 0.0 :history-penalty 2.0})

(deftest utility-equation
  (testing "U = P·G − C − penalty, without noise"
    (is (= 8.0 (actr/utility {:p 0.9 :c 1.0} quiet 0)))
    (is (= -1.0 (actr/utility {:p 0.9 :c 10.0} quiet 0))))
  (testing "history penalty subtracts linearly"
    (is (= 6.0 (actr/utility {:p 0.9 :c 1.0} quiet 2)))))

(deftest tabu-counts-keyed-by-operator
  (testing "counts from memory/record feed the tabu penalty"
    (let [rst {:op :restart :args {:service "payments"}}
          sc {:op :scale-out :args {:service "payments"}}
          est {rst {:p 0.9 :c 1.0} sc {:p 0.4 :c 1.0}}
          wm (-> (memory/wm {})
                 (memory/record rst (core/ok {} ""))
                 (memory/record rst (core/ok {} ""))
                 (memory/record rst (core/ok {} "")))]
      (is (= 3 (get (:counts wm) rst)))
      (is (= sc (:chosen (actr/select [rst sc] est (:counts wm) quiet 1)))))))

(deftest selection
  (let [estimates {a->b {:p 0.9 :c 1.0}
                   b->a {:p 0.2 :c 9.0}}]
    (testing "higher utility wins"
      (is (= a->b (:chosen (actr/select [a->b b->a] estimates {} quiet 1)))))
    (testing "operators without usable estimates sit out"
      (is (= b->a (:chosen (actr/select [a->b b->a] {a->b {:p nil :c 1.0} b->a {:p 0.5 :c 2.0}} {} quiet 1)))))
    (testing "noise makes close calls go either way"
      (is (= #{a->b b->a}
             (set (for [s (range 1 40)]
                    (:chosen (actr/select [a->b b->a] {a->b {:p 0.5 :c 0.0} b->a {:p 0.48 :c 0.0}}
                                          {} (assoc quiet :noise-s 1.0) (actr/seed s))))))))))

(deftest resolution-with-stub
  (testing "resolve picks the highest-utility candidate from estimates"
    (let [llm (llm/->StubLLM {a->b {:p 0.9 :c 1.0 :reasoning "clear win"}
                              b->a {:p 0.3 :c 8.0 :reasoning "long shot"}} nil)
          out (actr/resolve llm [a->b b->a] {} quiet 1)]
      (is (= a->b (:chosen out)))
      (is (= "clear win" (get-in out [:estimates a->b :reasoning])))))
  (testing "propose returns the stubbed operators for no-change impasses"
    (is (= [a->b] (llm/propose (llm/->StubLLM {} [a->b]) {})))))

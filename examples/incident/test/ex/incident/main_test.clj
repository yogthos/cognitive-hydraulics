(ns ex.incident.main-test
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.main :as main]
            [ex.incident.world :as world]
            [hyd.llm :as llm]
            [hyd.memory :as memory]))

(def rb (world/rollback "payments"))
(def rst (world/restart "payments"))
(def sc (world/scale-out "payments"))

(defn- counting-stub [estimates calls]
  (reify llm/Intuition
    (estimate [_ operators _]
      (swap! calls inc)
      (select-keys estimates operators))
    (propose [_ _] [])))

(def estimates {rb {:p 0.9 :c 2.0} rst {:p 0.3 :c 1.0} sc {:p 0.1 :c 1.0}})

(deftest cold-then-warm-offline
  (let [calls (atom 0)
        cold (main/run! (counting-stub estimates calls) :bad-config (memory/store))]
    (testing "cold: substates, then the valve hands the tie to the intuition"
      (is (:solved? cold))
      (is (= :ok (get-in cold [:final-state :services "payments" :health])))
      (is (= [:subgoal :subgoal :actr] (map second (:steps cold))))
      (is (= 1 @calls))
      (is (= 1 (count (:chunks (:store cold))))))
    (testing "warm: the chunk fires before any impasse, no LLM call"
      (reset! calls 0)
      (let [warm (main/run! (counting-stub estimates calls) :bad-config (:store cold))]
        (is (:solved? warm))
        (is (= [:chunk] (map second (:steps warm))))
        (is (zero? @calls))))
    (testing "a different root cause is a different situation: no chunk"
      (reset! calls 0)
      (let [leak (main/run! (counting-stub {rst {:p 0.9 :c 1.0} rb {:p 0.2 :c 2.0} sc {:p 0.1 :c 1.0}} calls)
                            :memory-leak (:store cold))]
        (is (:solved? leak))
        (is (not-any? #{:chunk} (map second (:steps leak))))))))

(deftest wrong-guess-is-rejected
  (testing "a remedy that changes nothing is an operator no-change: the next pick differs"
    (let [calls (atom 0)
          out (main/run! (counting-stub {rst {:p 0.9 :c 1.0} rb {:p 0.5 :c 2.0} sc {:p 0.1 :c 1.0}} calls)
                         :bad-config (memory/store))]
      (is (:solved? out))
      (is (= [:restart :rollback] (keep #(nth % 2) (:steps out))))
      (is (= 2 @calls))
      (is (= [rb] (map :op (:chunks (:store out))))))))

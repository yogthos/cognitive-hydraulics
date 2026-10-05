(ns ex.incident.world-test
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.world :as world]
            [hyd.agent :as agent]
            [hyd.llm :as llm]))

(deftest operator-semantics
  (testing "restart fixes a memory leak, not a bad deploy"
    (is (world/resolved? (world/apply-op (world/restart "payments")
                                         (world/incident :memory-leak))))
    (is (not (world/resolved? (world/apply-op (world/restart "payments")
                                              (world/incident :bad-config))))))
  (testing "rollback fixes a bad deploy, fails on a stale one"
    (is (world/resolved? (world/apply-op (world/rollback "payments")
                                         (world/incident :bad-config))))
    (is (not (:ok (world/apply-op (world/rollback "payments")
                                  (world/incident :bad-config 340))))))
  (testing "scale-out fixes capacity, nothing else"
    (is (world/resolved? (world/apply-op (world/scale-out "payments")
                                         (world/incident :capacity))))
    (is (not (world/resolved? (world/apply-op (world/scale-out "payments")
                                              (world/incident :bad-config))))))
  (testing "a human always resolves, at ruinous cost"
    (is (world/resolved? (world/apply-op (world/page-human "payments")
                                         (world/incident :bad-config))))))

(deftest goal-and-proposals
  (testing "a fresh incident is not resolved"
    (is (not (world/goal-met? (world/incident :bad-config) {:target #{"payments"}}))))
  (testing "the runbook proposes every remedy for the paged service, tied"
    (let [props (world/runbook-proposer (world/incident :bad-config) nil)
          ops (map #(get-in % [:op :op]) props)]
      (is (= [:restart :rollback :scale-out] ops))
      (is (apply = (map :priority props))))))

(defn- solve-stub [root-cause estimates]
  (agent/solve {:state (world/incident root-cause)
                :goal {:target #{"payments"}}
                :proposer world/runbook-proposer
                :apply world/apply-op
                :goal-met? world/goal-met?
                :intuition (llm/->StubLLM estimates nil)
                :params {:goal-value 10.0 :noise-stddev 0.0 :history-penalty 2.0}}))

(deftest decision-cycle-with-stub-intuition
  (testing "ties escalate to the intuition, which breaks them"
    (let [out (solve-stub :bad-config {(world/rollback "payments") {:p 0.9 :c 2.0}
                                       (world/restart "payments") {:p 0.3 :c 1.0}
                                       (world/scale-out "payments") {:p 0.1 :c 1.0}})]
      (is (:solved? out))
      (is (= :ok (get-in out [:final-state :services "payments" :health])))
      (is (nil? (get-in out [:final-state :page])))
      (is (some #(= :actr (:via %)) (:trace out)))
      (is (= 1 (count (:chunks out)))))))

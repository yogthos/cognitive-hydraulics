(ns ex.incident.lev-test
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.lev :as lev]
            [ex.incident.openai :as openai]
            [ex.incident.world :as world]))

(def rb (world/rollback "payments"))
(def rst (world/restart "payments"))
(def sc (world/scale-out "payments"))
(def ops [rst rb sc])

(deftest question-building
  (testing "one choice question, one criterion per operator, ids stable"
    (let [q (lev/questions ops)]
      (is (= "choice" (get-in q ["remedy" "type"])))
      (is (= #{(openai/op-id rb) (openai/op-id rst) (openai/op-id sc)}
             (set (keys (get-in q ["remedy" "criteria"])))))
      (is (string? (get-in q ["remedy" "instructions"]))))))

(deftest state-projection-hides-ground-truth
  (testing "the observability view carries the signals, never the cause"
    (let [s (lev/project-state (world/incident :bad-config))]
      (is (nil? (get-in s [:services "payments" :root-cause])))
      (is (= 14 (get-in s [:services "payments" :deploy :minutes-ago])))
      (is (= "latency p99 4.2s, error rate 9%" (get-in s [:page :signal])))
      (is (not (re-find #"root-cause" (pr-str s)))))))

(deftest answer-parsing
  (let [body (str "{\"answers\": {\"remedy\": {\"probabilities\": {"
                  "\"" (openai/op-id rb) "\": 0.9, "
                  "\"" (openai/op-id rst) "\": 0.08, "
                  "\"" (openai/op-id sc) "\": 0.02}}}}")]
    (testing "calibrated probabilities become P estimates, cost uniform"
      (let [est (lev/parse-answer body ops)]
        (is (= 0.9 (:p (get est rb))))
        (is (= 0.08 (:p (get est rst))))
        (is (= 1.0 (:c (get est rb))))))
    (testing "an operator the model never scored reads as p 0"
      (let [est (lev/parse-answer body [rst rb sc])]
        (is (pos? (count est)))))
    (testing "garbage answers empty"
      (is (= {} (lev/parse-answer "gateway timeout" ops))))
    (testing "missing probabilities answers empty"
      (is (= {} (lev/parse-answer
                 "{\"answers\": {\"remedy\": {\"choice\": \"x\"}}}"
                 ops))))))

(deftest request-building
  (testing "the systemone request carries state, questions and model"
    (let [req (lev/request {:state (world/incident :bad-config)}
                                       ops
                                       {:model "english"})]
      (is (= "english" (:model req)))
      (is (contains? (:questions req) "remedy"))
      (is (nil? (get-in req [:state :services "payments" :root-cause]))))))

(ns hyd.rules-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.rules :as rules]))

(def rule-book
  [(rules/rule "finish" (fn [s g] (= s (:target g))) :noop 9.0)
   (rules/rule "explore" (fn [s _] (:lost s)) :list 1.0)])

(deftest both-rules-fire-sorted
  (let [proposals (rules/propose rule-book
                                 {:lost true :on {:a :table}}
                                 {:target {:lost true :on {:a :table}}})]
    (is (= [:noop :list] (map #(get-in % [:op :op]) proposals)))))

(deftest only-finish-fires
  (let [proposals (rules/propose rule-book
                                 {:on {:a :b}}
                                 {:target {:on {:a :b}}})]
    (is (= [:noop] (map #(get-in % [:op :op]) proposals)))))

(deftest no-match-proposes-nothing
  (is (empty? (rules/propose rule-book {:on {:a :b}} {:target {}}))))

(deftest rule-name-carried
  (is (= "finish" (:rule (first (rules/propose rule-book {} {:target {}}))))))

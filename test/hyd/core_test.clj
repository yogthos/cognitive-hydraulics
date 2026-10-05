(ns hyd.core-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.core :as core]))

(deftest proposal-shape
  (testing "a proposal pairs an operator with a priority and the rule that made it"
    (let [p (core/proposal :move {:b :a :to :table} 4.0 "clear-a")]
      (is (= :move (get-in p [:op :op])))
      (is (= {:b :a :to :table} (get-in p [:op :args])))
      (is (= 4.0 (:priority p)))
      (is (= "clear-a" (:rule p))))))

(deftest result-constructors
  (testing "success carries the next state"
    (is (= {:ok true :state {:on {:a :table}} :note "moved"}
           (core/ok {:on {:a :table}} "moved"))))
  (testing "failure carries only an error"
    (is (= {:ok false :error "a is not clear"}
           (core/fail "a is not clear")))))

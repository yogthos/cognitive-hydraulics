(ns hyd.impasse-test
  (:require [clojure.test :refer [deftest is testing are]]
            [hyd.core :as core]
            [hyd.impasse :as impasse]))

(defn- prop [name priority]
  (core/proposal name {} priority (str name "-rule")))

(deftest detect-impasse
  (testing "no proposals is a no-change impasse"
    (is (= :state-no-change (:type (impasse/decide [])))))
  (testing "a single proposal is selected"
    (is (= :select (:type (impasse/decide [(prop :move 3.0)])))))
  (testing "a clear winner is selected wherever it is listed"
    (is (= :move (get-in (impasse/decide [(prop :stack 3.0) (prop :move 5.0)]) [:op :op]))))
  (testing "two proposals tied at the top are a tie impasse carrying both"
    (let [imp (impasse/decide [(prop :move 4.0) (prop :stack 4.0) (prop :discard 1.0)])]
      (is (= :tie (:type imp)))
      (is (= 2 (count (:candidates imp))))))

  (testing "ambiguity — share of proposals at or near the top"
    (are [expected ps] (= expected (impasse/ambiguity ps))
      1.0 []
      0.0 [(prop :move 1.0)]
      ;; all-equal at the top: full ambiguity
      1.0 [(prop :move 2.0) (prop :stack 2.0)]
      ;; clear separation: no ambiguity
      0.0 [(prop :move 5.0) (prop :stack 1.0)]))

  (testing "a near-tie counts the close contenders"
    ;; range 4, within-10% band = 4.6+, only the 5.0 qualifies
    (is (= 0.0 (impasse/ambiguity [(prop :move 5.0) (prop :stack 1.0) (prop :discard 0.5)])))
    ;; range 1, band 0.9+, both 5.0 and 4.95 are contenders: (2-1)/(3-1)
    (is (= 0.5 (impasse/ambiguity [(prop :move 5.0) (prop :stack 4.95) (prop :discard 4.0)])))))

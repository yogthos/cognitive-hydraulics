(ns hyd.pressure-test
  (:require [clojure.test :refer [deftest is testing are]]
            [hyd.core :as core]
            [hyd.pressure :as pressure]))

(def d core/defaults)

(deftest pressure-equation
  (testing "calm at zero load"
    (is (zero? (pressure/pressure {:depth 0 :time-ms 0 :impasses 0 :ambiguity 0.0} d))))
  (testing "max load saturates every component at 1"
    (is (= 1.0 (pressure/pressure {:depth 3 :time-ms 500 :impasses 3 :ambiguity 1.0} d))))
  (testing "components saturate individually at their thresholds"
    (is (= (pressure/pressure {:depth 3 :time-ms 0 :impasses 0 :ambiguity 0.0} d)
           (pressure/pressure {:depth 99 :time-ms 0 :impasses 0 :ambiguity 0.0} d)))))

(deftest fallback-threshold
  (testing "fallback fires at or above the threshold"
    (is (pressure/fallback? {:depth 2 :time-ms 500 :impasses 2 :ambiguity 1.0} d)))
  (testing "no fallback below"
    (is (not (pressure/fallback? {:depth 0 :time-ms 0 :impasses 0 :ambiguity 0.0} d))))
  (testing "the threshold is a param"
    (is (pressure/fallback? {:depth 1 :time-ms 0 :impasses 1 :ambiguity 1.0}
                            (assoc d :pressure-threshold 0.3)))))

(deftest monotonicity
  (testing "pressure is monotonic in each component"
    (let [base {:depth 1 :time-ms 100 :impasses 1 :ambiguity 0.2}]
      (is (< (pressure/pressure base d) (pressure/pressure (assoc base :depth 2) d)))
      (is (< (pressure/pressure base d) (pressure/pressure (assoc base :time-ms 300) d)))
      (is (< (pressure/pressure base d) (pressure/pressure (assoc base :impasses 2) d)))
      (is (< (pressure/pressure base d) (pressure/pressure (assoc base :ambiguity 0.8) d))))))

(deftest level-naming
  (are [lvl p] (= lvl (pressure/level p d))
    :calm 0.0
    :calm 0.29
    :elevated 0.3
    :elevated 0.49
    :high 0.5
    :high 0.69
    :critical 0.7
    :critical 1.0))

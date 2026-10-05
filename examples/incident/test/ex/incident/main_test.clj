(ns ex.incident.main-test
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.deepseek :as deepseek]
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
      estimates)
    (propose [_ _] [])))

(deftest run-bang-end-to-end-offline
  (let [calls (atom 0)
        store-atom (atom (memory/store))
        intuition (deepseek/chunk-aware
                   (counting-stub {rb {:p 0.9 :c 2.0}
                                   rst {:p 0.3 :c 1.0}
                                   sc {:p 0.1 :c 1.0}} calls)
                   store-atom)
        out (main/run! intuition :bad-config)]
    (is (:solved? out))
    (is (= :ok (get-in out [:final-state :services "payments" :health])))
    (is (pos? (count (:steps out))))
    (is (zero? (count (:chunks @store-atom))))
    (is (main/file-chunk! out store-atom (world/incident :bad-config)))
    (is (= 1 (count (:chunks @store-atom))))
    (is (= 1 @calls))))

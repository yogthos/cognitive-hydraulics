(ns ex.incident.deepseek-test
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.deepseek :as deepseek]
            [ex.incident.world :as world]
            [hyd.llm :as llm]
            [hyd.memory :as memory]))

(def rb (world/rollback "payments"))
(def rst (world/restart "payments"))

(defn- counting-stub [estimates calls]
  (reify llm/Intuition
    (estimate [_ operators _]
      (swap! calls inc)
      estimates)
    (propose [_ _] [])))

(deftest config-from-env
  (let [cfg (deepseek/config)]
    (is (= "https://api.deepseek.com" (:url cfg)))
    (is (string? (:model cfg)))
    (is (string? (:api-key cfg)))))

(deftest cold-store-calls-live
  (let [calls (atom 0)
        wrap (deepseek/chunk-aware (counting-stub {rb {:p 0.9 :c 2.0}} calls)
                                   (atom (memory/store)))]
    (is (= {:p 0.9 :c 2.0}
           (get (llm/estimate wrap [rb rst] {:state (world/incident :bad-config)}) rb)))
    (is (= 1 @calls))))

(deftest remembered-choice-skips-live
  (let [calls (atom 0)
        chunk {:state (world/incident :bad-config) :op rb
               :goal {:target #{"payments"}} :utility 7.0}
        store (atom (memory/remember (memory/store) chunk))
        wrap (deepseek/chunk-aware (counting-stub {} calls) store)
        ests (llm/estimate wrap [rb rst] {:state (world/incident :bad-config)})]
    (is (pos? (:p (get ests rb))))
    (is (nil? (get ests rst)))
    (is (zero? @calls))))

(deftest persist-roundtrip
  (let [path "/tmp/hyd-incident-chunks-test.edn"
        chunk {:state (world/incident :bad-config) :op rb
               :goal {:target #{"payments"}} :utility 7.0}
        store (memory/remember (memory/store) chunk)]
    (deepseek/save-store! store path)
    (is (= 1 (count (:chunks (deepseek/load-store path)))))))

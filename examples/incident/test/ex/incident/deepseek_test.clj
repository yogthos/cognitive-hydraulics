(ns ex.incident.deepseek-test
  (:require [clojure.test :refer [deftest is]]
            [ex.incident.deepseek :as deepseek]
            [ex.incident.world :as world]
            [hyd.memory :as memory]))

(def rb (world/rollback "payments"))

(deftest config-from-env
  (let [cfg (deepseek/config)]
    (is (= "https://api.deepseek.com" (:url cfg)))
    (is (string? (:model cfg)))))

(deftest persist-roundtrip
  (let [path "/tmp/hyd-incident-chunks-test.edn"
        store (memory/remember (memory/store)
                               (memory/chunk (world/incident :bad-config) rb
                                             {:target #{"payments"}} 7.0))]
    (deepseek/save-store! store path)
    (is (= store (deepseek/load-store path)))))

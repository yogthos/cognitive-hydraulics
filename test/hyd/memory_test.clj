(ns hyd.memory-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.core :as core]
            [hyd.memory :as memory]))

(defn- t [op ok]
  {:op {:op op :args {}} :result (if ok (core/ok {} "fine") (core/fail "boom"))})

(defn- apply-t [wm tr next-state]
  (memory/record wm tr (:result tr) next-state))

(deftest working-memory-basics
  (let [wm (-> (memory/wm {:step 0})
               (apply-t (t :move true) {:step 1})
               (apply-t (t :move false) {:step 1}))]
    (testing "records transitions and counts actions"
      (is (= 2 (count (:history wm))))
      (is (= {(:op (t :move true)) 2} (:counts wm))))
    (testing "state advances to the last ok result"
      (is (= {:step 1} (:state wm))))
    (testing "failed operators in the recent window"
      (is (= [:move] (memory/failed-operators wm))))
    (testing "loop detection: same op failing 3+ times"
      (is (false? (memory/looping? wm)))
      (is (true? (memory/looping? (-> wm
                                      (apply-t (t :move false) {:step 1})
                                      (apply-t (t :move false) {:step 1}))))))))

(deftest chunk-store
  (testing "a successful resolution becomes a chunk, retrievable by state similarity"
    (let [store (-> (memory/store)
                    (memory/remember {:state {:on {:a :table} :clear #{:a :b}}
                                      :op :move
                                      :goal "stack a on b"
                                      :utility 7.5}))]
      (is (= 1 (count (:chunks store))))
      (is (= :move (:op (first (memory/recall store {:on {:a :table}})))))))

  (testing "chunks persist to EDN and load back"
    (let [path "/tmp/hyd-chunks-test.edn"
          store (-> (memory/store)
                    (memory/remember {:state {:on {:a :table}} :op :stack :goal "g" :utility 3.0}))]
      (memory/save! store path)
      (is (= 1 (count (:chunks (memory/load-store path))))))))

(ns hyd.memory-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.core :as core]
            [hyd.memory :as memory]
            [hyd.persist :as persist]))

(def mv {:op :move :args {}})

(deftest working-memory-basics
  (let [wm (-> (memory/wm {:step 0})
               (memory/record mv (core/ok {:step 1} "fine"))
               (memory/record mv (core/fail "boom")))]
    (testing "records transitions and counts actions by whole operator"
      (is (= 2 (count (:history wm))))
      (is (= {mv 2} (:counts wm))))
    (testing "state advances to the last ok result"
      (is (= {:step 1} (:state wm))))
    (testing "operator no-change rejections are per state"
      (let [wm (memory/reject wm {:step 1} mv)]
        (is (memory/rejected? wm {:step 1} mv))
        (is (not (memory/rejected? wm {:step 0} mv)))))))

(deftest chunk-store
  (testing "a chunk keeps the whole operator and is recalled for its goal"
    (let [op {:op :move :args {:b :a :to :b}}
          store (memory/remember (memory/store) (memory/chunk {:on {:a :table}} op "g" 7.5))]
      (is (= op (:op (first (memory/recall store {:on {:a :table}} "g" 1.0)))))
      (is (empty? (memory/recall store {:on {:a :table}} "other" 0.0)))))
  (testing "similarity reads contents, not just keys"
    (is (< (memory/similarity {:on {:a :b}} {:on {:a :c}}) 1.0)))
  (testing "chunks persist to EDN and load back"
    (let [path "/tmp/hyd-chunks-test.edn"
          store (memory/remember (memory/store) (memory/chunk {:on {:a :table}} mv "g" 3.0))]
      (persist/save! store path)
      (is (= store (persist/load-store path))))))

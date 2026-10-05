(ns hyd.blocks-test
  (:require [clojure.test :refer [deftest is testing]]
            [hyd.core :as core]
            [hyd.blocks :as blocks]))

(def world
  {:on {:a :table :b :table :c :a}})

(deftest move-semantics
  (testing "moving a clear block to the table"
    (is (= {:ok true :state {:on {:a :table :b :table}}}
           (dissoc (blocks/apply-op {:op :move :args {:b :a :to :table}}
                                    {:on {:a :b :b :table}})
                   :note))))
  (testing "moving a clear block onto another clear block"
    (is (= {:on {:a :b :b :table}}
           (:state (blocks/apply-op {:op :move :args {:b :a :to :b}} {:on {:a :table :b :table}})))))
  (testing "a block with something on it cannot move"
    (is (not (:ok (blocks/apply-op {:op :move :args {:b :a :to :table}} world)))))
  (testing "cannot stack onto a non-clear destination"
    (is (not (:ok (blocks/apply-op {:op :move :args {:b :b :to :a}} world))))))

(deftest clear-computation
  (testing "clear blocks have nothing on them"
    (is (= #{:b :c :table} (blocks/clear world)))))

(deftest goal-test
  (testing "goal met when every named block is where it wants to be"
    (is (blocks/goal-met? {:on {:a :b}} {:target {:a :b}}))
    (is (not (blocks/goal-met? world {:target {:b :a}})))))

(ns hyd.blocks
  "The blocks world: the reference domain.

  State is {:on {block support}} — a is on the table, c on a. The floor is
  :table, always there and never moved. An operator moves one clear block
  onto a clear support. The goal says where some blocks should end up."
  (:require [hyd.core :as core]))

(defn clear
  "The blocks with nothing on them, plus :table."
  [state]
  (let [on (:on state)
        occupied (set (vals on))]
    (conj (clojure.set/difference (set (keys on)) occupied) :table)))

(defn- free?
  [state b]
  (contains? (clear state) b))

(defn apply-op
  "Apply a :move operator. Fails when b is not clear, to is not clear, b is
  the table, or b is already there."
  [{:keys [op args] :as operator} state]
  (let [{:keys [b to]} args
        on (:on state)]
    (cond
      (= b :table) (core/fail "the table does not move")
      (= b to) (core/fail "already there")
      (= (get on b) to) (core/fail "already there")
      (not (contains? on b)) (core/fail (str "no such block: " b))
      (not (free? state b)) (core/fail (str b " is not clear"))
      (not (free? state to)) (core/fail (str to " is not clear"))
      :else (core/ok (update state :on assoc b to)
                     (str "moved " b " onto " to)))))

(defn goal-met?
  "True when every block the goal names sits where it wants."
  [state goal]
  (let [target (:target goal)]
    (every? (fn [[b support]] (= support (get-in state [:on b]))) target)))

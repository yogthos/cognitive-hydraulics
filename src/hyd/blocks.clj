(ns hyd.blocks
  "The blocks world: the reference domain.

  State is {:on {block support}} — a is on the table, c on a. The floor is
  :table, always there and never moved. An operator moves one clear block
  onto a clear support. The goal says where some blocks should end up."
  (:require [clojure.set :as set]
            [hyd.core :as core]))

(defn clear
  "The blocks with nothing on them, plus :table."
  [state]
  (let [on (:on state)
        occupied (set (vals on))]
    (conj (set/difference (set (keys on)) occupied) :table)))

(defn- free?
  [state b]
  (contains? (clear state) b))

(defn apply-op
  "Apply a :move operator. Fails when b is not clear, to is not clear, b is
  the table, or b is already there."
  [{:keys [args]} state]
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
  (every? (fn [[b support]] (= support (get-in state [:on b]))) (:target goal)))

(defn legal-moves
  "Every move that actually relocates a clear block onto a clear support
  (never onto itself, never to where it already sits)."
  [state]
  (let [clear (clear state)
        on (:on state)]
    (for [b (disj clear :table)
          to clear
          :when (and (not= to b)
                     (not= to (get on b)))]
      {:op :move :args {:b b :to to}})))

(defn naive-proposer
  "The naive rule book: every legal move at equal priority, so the symbolic
  layer ties and impasse handling does the interesting work."
  [state _goal]
  (map #(core/proposal :move (:args %) 1.0 "legal-move")
       (legal-moves state)))

(defn goal-directed-proposer
  "A rule book that knows the goal: move each goal-named block onto its
  goal support when both are free. With one goal block it solves without
  an impasse; several free goal moves at once tie."
  [state goal]
  (let [clear (clear state)
        on (:on state)]
    (for [[b support] (:target goal)
          :when (and (contains? on b)
                     (not= support (get on b))
                     (contains? clear b)
                     (or (= support :table) (contains? clear support)))]
      (core/proposal :move {:b b :to support} 1.0 "goal-move"))))

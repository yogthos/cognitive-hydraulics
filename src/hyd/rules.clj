(ns hyd.rules
  "Production rules as data.

  A rule is {:name, :when (state goal) -> bool, :op, :priority}. The book is
  a vector; proposing is filtering and sorting. Rules never see the LLM, the
  clock, or IO — the agent feeds them state and goal."
  (:require [hyd.core :as core]))

(defn rule
  "A production rule: when the condition holds, propose op at priority."
  [name when op priority]
  {:name name :when when :op op :priority priority})

(defn propose
  "Every matching rule's proposal, highest priority first."
  [book state goal]
  (->> book
       (filter #((:when %) state goal))
       (map #(core/proposal (:op %) {} (:priority %) (:name %)))
       (sort-by :priority >)))

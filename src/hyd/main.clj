(ns hyd.main
  "CLI: run the blocks-world demo through the decision cycle.

    jolt -M:run                  # goal-directed rules: solves without impasses
    jolt -M:run --naive          # naive rules, no model: substates nest until
                                 # the valve opens and System 1 picks
    jolt -M:run --lookahead      # naive rules with a model: System 2
                                 # deliberates by look-ahead
  "
  (:require [hyd.agent :as agent]
            [hyd.blocks :as blocks]
            [hyd.llm :as llm]))

(def ^:private smart-stub
  "The demo's stand-in intuition: knows the goal move."
  (llm/->StubLLM {{:op :move :args {:b :a :to :b}} {:p 0.9 :c 1.0 :reasoning "a onto b"}}
                 nil))

(def ^:private demo
  {:state {:on {:a :table :b :table :c :table}}
   :goal {:target {:a :b}}
   :apply blocks/apply-op
   :goal-met? blocks/goal-met?
   :intuition smart-stub
   :params {:noise-s 0.0}})

(defn- task
  [args]
  (cond
    (some #{"--lookahead"} args) (assoc demo :proposer blocks/naive-proposer
                                        :simulate blocks/apply-op)
    (some #{"--naive"} args) (assoc demo :proposer blocks/naive-proposer)
    :else (assoc demo :proposer blocks/goal-directed-proposer)))

(defn- fmt
  [x]
  (if (float? x) (format "%.2f" x) (str x)))

(defn -main [& args]
  (let [out (agent/solve (task args))]
    (println "solved:" (:solved? out))
    (println "final:" (:final-state out))
    (println "cycles:" (:cycles out) "chunks:" (count (:chunks out)))
    (doseq [t (:trace out)]
      (println " " (:cycle t) (:via t)
               (if-let [op (:op t)] (str (:op op) " " (:args op)) "-")
               (if (:impasse t)
                 (str "(" (name (:impasse t)) ", depth " (:depth t)
                      ", pressure " (fmt (:pressure t)) ")")
                 "")))))

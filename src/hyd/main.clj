(ns hyd.main
  "CLI: run the blocks-world demo through the decision cycle.

    jolt -M:run                  # goal-directed rules: solves without impasses
    jolt -M:run --naive          # naive rules: ties escalate to System 1
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
   :params {:goal-value 10.0 :noise-stddev 0.0 :history-penalty 2.0}})

(defn -main [& args]
  (let [naive? (some #{"--naive"} args)
        out (agent/solve (assoc demo
                                :proposer (if naive?
                                            agent/blocks-proposer
                                            agent/goal-directed-proposer)))]
    (println "solved:" (:solved? out))
    (println "final:" (:final-state out))
    (println "cycles:" (:cycles out) "chunks:" (count (:chunks out)))
    (doseq [t (:trace out)]
      (println " " (:cycle t) (:via t) (:op t) (:args t)))))

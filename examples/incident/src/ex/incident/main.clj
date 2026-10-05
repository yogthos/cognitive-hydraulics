(ns ex.incident.main
  "One on-call shift, end to end.

    jolt -M:run            triage the incident (uses/maintains chunks.edn)
    jolt -M:run --reset    forget the chunks first (cold demo)
    jolt -M:run memory-leak   pick the scenario: bad-config (default),
                              memory-leak, capacity

  First run on a cold store: the runbook ties, pressure climbs, the valve
  hands the tie to DeepSeek, the fix lands and is remembered. Second run on
  a warm store: the chunk answers before the LLM is ever called."
  (:require [clojure.java.io :as io]
            [ex.incident.deepseek :as deepseek]
            [ex.incident.lev :as lev]
            [ex.incident.world :as world]
            [hyd.agent :as agent]
            [hyd.core :as core]
            [hyd.llm :as llm]
            [hyd.memory :as memory]))

(def store-path "chunks.edn")

(defn- counting
  "An intuition that counts how often the live model was actually reached."
  [inner calls]
  (reify llm/Intuition
    (estimate [_ operators ctx]
      (swap! calls inc)
      (llm/estimate inner operators ctx))
    (propose [_ ctx]
      (llm/propose inner ctx))))

(defn run!
  "One shift: triage the scenario with the given intuition. Returns the solve
  report with a printable :steps seq of [cycle via op] added."
  [intuition scenario]
  (let [out (agent/solve {:state (world/incident scenario)
                          :goal {:target #{"payments"}}
                          :proposer world/runbook-proposer
                          :apply world/apply-op
                          :goal-met? world/goal-met?
                          :intuition intuition
                          :params (merge core/defaults {:noise-stddev 0.0})})]
    (assoc out :steps (map (fn [t] [(:cycle t) (:via t) (:op t)]) (:trace out)))))

(defn file-chunk!
  "File the winning heuristic resolution as a chunk, but only when it
  actually worked: the last :actr step of a solved run, and not one that
  is already remembered for a state this similar."
  [out store-atom initial-state]
  (when (:solved? out)
    (when-let [winner (some #(when (= :actr (:via %)) %) (reverse (:trace out)))]
      (let [op {:op (:op winner) :args (:args winner)}]
        (when-not (some #(= (:op %) op) (memory/recall @store-atom initial-state))
          (swap! store-atom memory/remember
                 {:state initial-state :op op :goal nil :utility 7.0}))))))

(defn report!
  "Print a run report; returns the report map."
  [out calls chunks-before chunks-after]
  (println (str "llm calls: " @calls))
  (println (str "cycles: " (:cycles out) ", solved: " (:solved? out)))
  (doseq [[c via op] (:steps out)]
    (println (str "  cycle " c ": " (name via) " -> " (if op (name op) "-"))))
  (println (str "chunks: " chunks-before " -> " chunks-after))
  (println (str "payments health: "
                (get-in out [:final-state :services "payments" :health])))
  out)

(defn -main
  [& args]
  (when (some #(= % "--reset") args)
    (.delete (io/file store-path))
    (println (str "store reset: " store-path)))
  (let [mood (or (some #{"--lev" "--deepseek"} args) "--deepseek")
        scenario (keyword (or (first (remove #(contains? #{"--reset" "--lev" "--deepseek"} %) args))
                              "bad-config"))
        store-atom (atom (deepseek/load-store store-path))
        chunks-before (count (:chunks @store-atom))
        calls (atom 0)
        lev-url (str "http://127.0.0.1:" (or (System/getenv "LEV_PORT") "8080"))
        live (if (= mood "--lev")
               (lev/->LevLLM (or (System/getenv "LEV_URL") lev-url)
                             {:model (or (System/getenv "LEV_MODEL") "english")})
               (deepseek/live))
        label (if (= mood "--lev")
                (str "lev/" (or (System/getenv "LEV_MODEL") "english"))
                (:model (deepseek/config)))
        intuition (deepseek/chunk-aware (counting live calls) store-atom)
        out (run! intuition scenario)]
    (println (str "scenario: " (name scenario) ", intuition: " label))
    (file-chunk! out store-atom (world/incident scenario))
    (let [chunks-after (count (:chunks @store-atom))]
      (report! out calls chunks-before chunks-after))
    (deepseek/save-store! @store-atom store-path)))

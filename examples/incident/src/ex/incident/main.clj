(ns ex.incident.main
  "One on-call shift, end to end.

    jolt -M:run            triage the incident (uses/maintains chunks.edn)
    jolt -M:run --reset    forget the chunks first (cold demo)
    jolt -M:run memory-leak   pick the scenario: bad-config (default),
                              memory-leak, capacity

  First run on a cold store: the runbook ties, the substates nest with no
  model to deliberate with, pressure opens the valve, DeepSeek estimates
  the remedies and ACT-R picks; a remedy that does nothing is rejected and
  the next is picked; the fix lands and is chunked. Second run on a warm
  store: the chunk fires as a learned preference before any impasse, and
  the LLM is never called."
  (:require [clojure.java.io :as io]
            [ex.incident.deepseek :as deepseek]
            [ex.incident.lev :as lev]
            [ex.incident.world :as world]
            [hyd.agent :as agent]
            [hyd.llm :as llm]))

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
  "One shift: triage the scenario with the given intuition and chunk store.
  Returns the solve report with a printable :steps seq of [cycle via op]
  added; the report's :store holds whatever was learned."
  [intuition scenario store]
  (let [out (agent/solve {:state (world/incident scenario)
                          :goal {:target #{"payments"}}
                          :proposer world/runbook-proposer
                          :apply world/apply-op
                          :goal-met? world/goal-met?
                          :intuition intuition
                          :store store
                          :params {:noise-s 0.0}})]
    (assoc out :steps (map (fn [t] [(:cycle t) (:via t) (:op (:op t))]) (:trace out)))))

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
        store (deepseek/load-store store-path)
        chunks-before (count (:chunks store))
        calls (atom 0)
        lev-url (str "http://127.0.0.1:" (or (System/getenv "LEV_PORT") "8080"))
        live (if (= mood "--lev")
               (lev/->LevLLM (or (System/getenv "LEV_URL") lev-url)
                             {:model (or (System/getenv "LEV_MODEL") "english")})
               (deepseek/live))
        label (if (= mood "--lev")
                (str "lev/" (or (System/getenv "LEV_MODEL") "english"))
                (:model (deepseek/config)))
        out (run! (counting live calls) scenario store)]
    (println (str "scenario: " (name scenario) ", intuition: " label))
    (report! out calls chunks-before (count (:chunks (:store out))))
    (deepseek/save-store! (:store out) store-path)))

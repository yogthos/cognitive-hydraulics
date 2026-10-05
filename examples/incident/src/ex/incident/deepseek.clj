(ns ex.incident.deepseek
  "DeepSeek as the intuition engine, wrapped in the chunk store.

  The wrapper sits between the decision loop and the live LLM: on every
  estimate request it first tries the chunk store - memories of what worked
  in states shaped like this one. A hit answers from memory and the live
  model is never called. A miss falls through to DeepSeek, and the operator
  it favored gets filed as a new chunk, so the same situation never costs a
  second call.

  The store is an atom held by the caller."
  (:require [ex.incident.openai :as openai]
            [hyd.llm :as llm]
            [hyd.memory :as memory]))

(defn config
  "The DeepSeek endpoint config, from the environment."
  []
  {:url "https://api.deepseek.com"
   :model (or (System/getenv "DEEPSEEK_MODEL") "deepseek-chat")
   :api-key (System/getenv "DEEPSEEK_API_KEY")})

(defn live
  "The real intuition: DeepSeek through the OpenAI-compatible adapter."
  ([] (live (config)))
  ([cfg] (openai/->OpenAILLM cfg)))

(defn- best-chunk
  "The most similar remembered chunk whose operator is on the table and has
  not already been applied twice: past that the tabu penalty should win,
  so the chunk steps aside and the live model is asked again."
  [store operators state counts]
  (->> (memory/recall store state)
       (filter #(let [op (:op %)]
                  (and (contains? (set operators) op)
                       (< (get counts op 0) 2))))
       (first)))

(defn chunk-aware
  "Wrap an intuition with the chunk store. A recalled chunk answers straight
  from memory and the live model is never called; otherwise the wrapped
  intuition is consulted. Chunks are the caller's business: an estimate is
  not a memory, so filing happens when a resolution actually works (see
  ex.incident.main/file-chunk!)."
  [inner store-atom]
  (reify llm/Intuition
    (estimate [_ operators ctx]
      (let [store @store-atom
            state (:state ctx)
            hit (best-chunk store operators state (or (:counts ctx) {}))]
        (if hit
          {(:op hit) {:p (/ (:utility hit) 10.0) :c 0.0}}
          (llm/estimate inner operators ctx))))
    (propose [_ ctx]
      (llm/propose inner ctx))))

(defn save-store!
  "Persist the store to EDN."
  [store path]
  (memory/save! store path))

(defn load-store
  "Read the store back, empty when absent."
  [path]
  (memory/load-store path))

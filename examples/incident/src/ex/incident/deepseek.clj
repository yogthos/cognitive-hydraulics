(ns ex.incident.deepseek
  "DeepSeek as the intuition engine, and the chunk store's file.

  The live model sits behind the pressure valve: the decision cycle only
  asks it when System 1 fires. Chunks are the library's business — solve
  recalls them as learned preferences before any impasse, so a remembered
  situation never reaches the model — and this namespace just keeps them
  on disk between shifts."
  (:require [ex.incident.openai :as openai]
            [hyd.persist :as persist]))

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

(defn save-store!
  "Persist the store to EDN."
  [store path]
  (persist/save! store path))

(defn load-store
  "Read the store back, empty when absent."
  [path]
  (persist/load-store path))

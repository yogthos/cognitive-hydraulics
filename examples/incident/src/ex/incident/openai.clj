(ns ex.incident.openai
  "The OpenAI-compatible inference engine, as an example-owned adapter.

  One adapter covers OpenAI, DeepSeek, and any local llama-server / vLLM
  endpoint: they all speak the chat-completions wire format. It satisfies
  hyd.llm/Intuition, which is the library's only seam to a model — the
  library itself does no IO. Everything testable is pure; the HTTP call
  is a thin shell around jolt.http-client."
  (:require ;; the java.time shim must load before http-client (RFC 0014)
            [jolt.time]
            [clojure.data.json :as json]
            [clojure.string :as str]
            [hyd.llm :as llm]
            [jolt.http-client :as http]))

(defn op-id
  "A stable string id for an operator: move|block|dest."
  [{:keys [op args] :as operator}]
  (str (name op) "|" (str/join "|" (map name (vals args)))))

(defn estimate-payload
  "The chat-completions request asking for probability/cost estimates of
  each operator, as JSON. Keys use the wire spelling (response_format):
  kebab-case would serialize to a name the endpoint ignores."
  [operators ctx]
  {:temperature 0
   :response_format {:type "json_object"}
   :messages
   [{:role :system
     :content (str "You estimate the value of actions for a planning agent. "
                   "Reply with a single JSON object mapping each operator id "
                   "to {\"p\": probability of success in [0,1], \"c\": cost}. "
                   "No other text.")}
    {:role :user
     :content (json/write-str
               {:state (:state ctx)
                :operators (map (fn [op] {:id (op-id op) :operator op}) operators)})}]})

(defn parse-estimates
  "The JSON reply back to {operator {:p :c}}. Operator ids are matched back
  to the operators asked about; unknown ids and estimates that are not
  numbers are dropped; garbage is {}."
  [reply operators]
  (try
    (let [by-id (into {} (map (juxt op-id identity) operators))
          decoded (json/read-str reply)]
      (into {}
            (keep (fn [[k v]]
                    (when-let [op (get by-id (str k))]
                      (when (and (map? v) (number? (get v "p")) (number? (get v "c")))
                        {op {:p (double (get v "p")) :c (double (get v "c"))}})))
                  decoded)))
    (catch Throwable _ {})))

(defn reply-content
  "The assistant text out of a raw HTTP response map, or nil when the status
  is not 2xx or the body is not a chat-completions reply."
  [resp]
  (let [status (:status resp)]
    (when (and status (<= 200 status 299))
      (try
        (get-in (json/read-str (str (:body resp))) ["choices" 0 "message" "content"])
        (catch Throwable _ nil)))))

(defrecord OpenAILLM [config]
  llm/Intuition
  (estimate [_ operators ctx]
    (let [{:keys [url model api-key]} config
          payload (estimate-payload operators ctx)
          resp (http/post (str url "/chat/completions")
                          {:headers {"Authorization" (str "Bearer " api-key)
                                     "Content-Type" "application/json"}
                           :body (json/write-str (assoc payload :model model))})
          content (reply-content resp)]
      (if content
        (parse-estimates content operators)
        {})))
  (propose [_ ctx]
    ;; generation is a future refinement; empty keeps the cycle honest
    []))

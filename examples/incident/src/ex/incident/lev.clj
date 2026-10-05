(ns ex.incident.lev
  "Lev (jlt-commons/lev) as the intuition engine.

  Lev answers typed questions over a state with calibrated probabilities:
  a choice question over the operators' ids is exactly hyd's estimate
  request, with probabilities an ACT-R equation can consume directly and a
  512-token budget instead of a chat context. The operator ids reuse
  ex.incident.openai/op-id so both inference engines key identically.

  The state the model sees is projected: services, page and deploy facts,
  never the hidden :root-cause — the same observability view an on-call
  has, so the demo stays honest."
  (:require ;; the java.time shim must load before http-client (RFC 0014)
            [jolt.time]
            [clojure.data.json :as json]
            [clojure.string :as str]
            [ex.incident.openai :as openai]
            [hyd.llm :as llm]
            [jolt.http-client :as http]))

(defn project-state
  "The observability view of an incident: health, deploys, the page and the
  restart count. :root-cause is the ground truth the decision is about, so
  it never reaches the model."
  [state]
  (into {}
        (map (fn [[k v]]
               (case k
                 :services [k (into {}
                                    (map (fn [[n svc]]
                                           [n (dissoc svc :root-cause)]))
                                    v)]
                 [k v])))
        state))

(defn questions
  "One choice question whose criteria are the operators, keyed by their
  stable op-id. An ordered map keeps option order deterministic."
  [operators]
  (let [criteria (apply array-map
                        (mapcat (fn [op] [(openai/op-id op)
                                          (str (name (get op :op)) " "
                                               (pr-str (get op :args)))])
                                operators))]
    {"remedy" {"type" "choice"
               "instructions" "Which remedy fits this paged service? Judge from the error signal, deploy freshness and what the deploy touched."
               "criteria" criteria}}))

(defn request
  "The /v1/systemone request body."
  [ctx operators {:keys [model] :or {model "english"} :as _opts}]
  {:model model
   :state (project-state (:state ctx))
   :questions (questions operators)})

(defn parse-answer
  "The reply back to {operator {:p :c}}: the choice probabilities become
  P estimates at uniform cost. Operators the model never scored get p 0;
  garbage answers {}."
  [reply operators]
  (try
    (let [probs (get-in (json/read-str reply) ["answers" "remedy" "probabilities"])]
      (if (map? probs)
        (into {}
              (map (fn [op]
                     (let [p (get probs (openai/op-id op))]
                       {op {:p (if (number? p) (double p) 0.0) :c 1.0}})))
              operators)
        {}))
    (catch Throwable _ {})))

(defn estimate!
  "One live call against the lev server."
  [url opts operators ctx]
  (let [resp (http/post (str url "/v1/systemone")
                        {:headers {"Content-Type" "application/json"}
                         :body (json/write-str (request ctx operators opts))})
        status (:status resp)]
    (if (and status (<= 200 status 299))
      (parse-answer (str (:body resp)) operators)
      {})))

(defrecord LevLLM [url opts]
  llm/Intuition
  (estimate [_ operators ctx]
    (estimate! url opts operators ctx))
  (propose [_ _ctx]
    []))

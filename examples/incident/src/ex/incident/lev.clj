(ns ex.incident.lev
  "Lev (jlt-commons/lev) as the intuition engine.

  ACT-R's U = P·G − C wants, per operator, the probability that it works
  and what it costs. Lev answers typed questions over a state with
  calibrated probabilities, all of a call's questions in one pass, so each
  operator gets two: a noul (will it resolve the page? its own P, not a
  share of one choice, so the estimates need not sum to 1) and a score
  over low / medium / high cost, read as an expected cost. The question
  ids reuse ex.incident.openai/op-id so both engines key identically.
  With :escalate {\"model\" thinker \"threshold\" t} the answers lev's
  encoder is unsure of are re-asked on a thinker (lev's escalate
  pattern).

  The state the model sees is projected: services, page and deploy facts,
  never the hidden :root-cause — the same observability view an on-call
  has, so the demo stays honest."
  (:require ;; the java.time shim must load before http-client (RFC 0014)
            [jolt.time]
            [clojure.data.json :as json]
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

(defn works-id "The id of an operator's will-it-work question." [op] (str (openai/op-id op) "/works"))
(defn cost-id "The id of an operator's cost question." [op] (str (openai/op-id op) "/cost"))

(def cost-levels ["low" "medium" "high"])

(def default-level-costs
  "What each cost level costs, against a goal worth 10 (core/defaults)."
  [0.5 1.0 2.0])

(defn- describe [op]
  (str (name (get op :op)) " " (pr-str (get op :args))))

(defn questions
  "Per operator, in operator order: a noul asking whether it resolves the
  page and a score asking what it costs. An ordered map keeps the order
  deterministic."
  [operators]
  (apply array-map
         (mapcat (fn [op]
                   [(works-id op) {"type" "noul"
                                   "instructions" (str "Will running `" (describe op) "` resolve this page? "
                                                       "Judge from the error signal, deploy freshness and what the deploy touched.")}
                    (cost-id op) {"type" "score"
                                  "instructions" (str "How costly or disruptive is running `" (describe op) "` right now?")
                                  "criteria" cost-levels}])
                 operators)))

(defn request
  "The /v1/systemone request body."
  [ctx operators {:keys [model escalate] :or {model "english"}}]
  (cond-> {:model model
           :state (project-state (:state ctx))
           :questions (questions operators)}
    escalate (assoc :escalate escalate)))

(defn- expected-cost [answer level-costs]
  (let [probs (get answer "probabilities")]
    (when (map? probs)
      (reduce + 0.0 (map-indexed (fn [i c] (* (double c) (double (or (get probs (str i)) 0.0)))) level-costs)))))

(defn parse-answer
  "The reply back to {operator {:p :c}}: the noul is P, the cost score's
  expectation over :level-costs (default-level-costs) is C, unit cost when
  it is missing. An operator without a noul sits out; garbage answers {}."
  ([reply operators] (parse-answer reply operators nil))
  ([reply operators {:keys [level-costs] :or {level-costs default-level-costs}}]
   (try
     (let [answers (get (json/read-str reply) "answers")]
       (if (map? answers)
         (into {}
               (keep (fn [op]
                       (let [p (get-in answers [(works-id op) "noul"])]
                         (when (number? p)
                           [op {:p (double p)
                                :c (or (expected-cost (get answers (cost-id op)) level-costs) 1.0)}]))))
               operators)
         {}))
     (catch Throwable _ {}))))

(defn estimate!
  "One live call against the lev server."
  [url opts operators ctx]
  (let [resp (http/post (str url "/v1/systemone")
                        {:headers {"Content-Type" "application/json"}
                         :body (json/write-str (request ctx operators opts))})
        status (:status resp)]
    (if (and status (<= 200 status 299))
      (parse-answer (str (:body resp)) operators opts)
      {})))

(defrecord LevLLM [url opts]
  llm/Intuition
  (estimate [_ operators ctx]
    (estimate! url opts operators ctx))
  (propose [_ _ctx]
    []))

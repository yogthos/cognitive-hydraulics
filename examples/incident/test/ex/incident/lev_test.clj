(ns ex.incident.lev-test
  (:require ;; the java.time shim must load before data.json (RFC 0014)
            [jolt.time]
            [clojure.data.json :as json]
            [clojure.test :refer [deftest is testing]]
            [ex.incident.lev :as lev]
            [ex.incident.openai :as openai]
            [ex.incident.world :as world]))

(def rb (world/rollback "payments"))
(def rst (world/restart "payments"))
(def sc (world/scale-out "payments"))
(def ops [rst rb sc])

(deftest question-building
  (let [q (lev/questions ops)]
    (testing "per operator, a noul for P(it works) and a score for its cost"
      (is (= (count q) 6))
      (doseq [op ops]
        (is (= "noul" (get-in q [(lev/works-id op) "type"])))
        (is (= "score" (get-in q [(lev/cost-id op) "type"])))
        (is (= ["low" "medium" "high"] (get-in q [(lev/cost-id op) "criteria"])))
        (is (re-find #"rollback|restart|scale-out" (get-in q [(lev/works-id op) "instructions"])))))
    (testing "ids derive from the shared op-id, in operator order"
      (is (= (lev/works-id rb) (str (openai/op-id rb) "/works")))
      (is (= [(lev/works-id rst) (lev/cost-id rst)] (take 2 (keys q)))))))

(deftest state-projection-hides-ground-truth
  (testing "the observability view carries the signals, never the cause"
    (let [s (lev/project-state (world/incident :bad-config))]
      (is (nil? (get-in s [:services "payments" :root-cause])))
      (is (= 14 (get-in s [:services "payments" :deploy :minutes-ago])))
      (is (re-find #"since the last deploy" (get-in s [:page :signal])))
      (is (not (re-find #"root-cause" (pr-str s)))))))

(defn- reply [answers] (json/write-str {"answers" answers}))

(defn- cost-answer [p-low p-med p-high]
  {"type" "score" "probabilities" {"0" p-low "1" p-med "2" p-high}})

(deftest answer-parsing
  (let [body (reply {(lev/works-id rb) {"type" "noul" "noul" 0.9}
                     (lev/cost-id rb) (cost-answer 0.0 1.0 0.0)
                     (lev/works-id rst) {"type" "noul" "noul" 0.08}
                     (lev/cost-id rst) (cost-answer 1.0 0.0 0.0)
                     (lev/works-id sc) {"type" "noul" "noul" 0.3}
                     (lev/cost-id sc) (cost-answer 0.0 0.5 0.5)})]
    (testing "each noul is that operator's own P; probabilities need not sum to 1"
      (let [est (lev/parse-answer body ops)]
        (is (= 0.9 (:p (get est rb))))
        (is (= 0.08 (:p (get est rst))))
        (is (= 0.3 (:p (get est sc))))))
    (testing "cost is the expected level cost: low 0.5, medium 1, high 2"
      (let [est (lev/parse-answer body ops)]
        (is (= 1.0 (:c (get est rb))))
        (is (= 0.5 (:c (get est rst))))
        (is (= 1.5 (:c (get est sc))))))
    (testing "the level costs are the caller's"
      (is (= 10.0 (:c (get (lev/parse-answer body ops {:level-costs [10 20 30]}) rst))))))
  (testing "an operator the model did not answer sits out"
    (let [est (lev/parse-answer (reply {(lev/works-id rb) {"type" "noul" "noul" 0.9}}) ops)]
      (is (= [rb] (keys est)))
      (is (= 1.0 (:c (get est rb))) "no cost answer: unit cost")))
  (testing "garbage answers empty"
    (is (= {} (lev/parse-answer "gateway timeout" ops)))
    (is (= {} (lev/parse-answer (reply {"x" 1}) ops)))))

(deftest request-building
  (testing "the systemone request carries the projected state, questions and model"
    (let [req (lev/request {:state (world/incident :bad-config)} ops {:model "english"})]
      (is (= "english" (:model req)))
      (is (contains? (:questions req) (lev/works-id rb)))
      (is (nil? (get-in req [:state :services "payments" :root-cause])))
      (is (not (contains? req :escalate)))))
  (testing "escalation to a thinker rides along when asked for"
    (let [req (lev/request {:state (world/incident :bad-config)} ops
                           {:model "english" :escalate {"model" "qwen3.5-4b" "threshold" 0.8}})]
      (is (= {"model" "qwen3.5-4b" "threshold" 0.8} (:escalate req))))))

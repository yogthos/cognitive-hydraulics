(ns ex.incident.world
  "The incident-triage domain: cognitive-hydraulics as an on-call decision
  maker.

  A page fires on a service. The runbook rules know every remedy — restart,
  rollback, scale out, page a human — and propose them all, tied: the
  symbolic layer cannot tell which one fits. What distinguishes them is the
  root cause, which the rules cannot see. The observability signals (what
  the last deploy touched, how old it is, the shape of the error) are in the
  state, and that is what the intuition engine reads.

  Hidden from the rules, carried as :root-cause, is the ground truth: a
  remedy resolves the page only when it matches the cause."
  (:require [hyd.core :as core]))

(defn incident
  "A world with a page on payments. root-cause is the hidden ground truth
  (:bad-config, :memory-leak, :capacity); deploy-minutes-ago controls how
  fresh the last deploy is (default 14, well inside the rollback window)."
  ([root-cause] (incident root-cause 14))
  ([root-cause deploy-minutes-ago]
   {:services {"payments" {:health :critical
                           :root-cause root-cause
                           :restarts 0
                           :deploy {:sha "a1b2c3"
                                    :minutes-ago deploy-minutes-ago
                                    :touched ["config/limits.toml" "src/api.clj"]}}
              "orders" {:health :ok
                        :root-cause nil
                        :restarts 0
                        :deploy {:sha "9f8e7d"
                                 :minutes-ago 340
                                 :touched ["src/core.clj"]}}}
    :page {:service "payments"
           :signal "latency p99 4.2s, error rate 9%"
           :minutes-ago 6}}))

;; --- operators, as data -----------------------------------------------------

(defn restart [service] {:op :restart :args {:service service}})
(defn rollback [service] {:op :rollback :args {:service service}})
(defn scale-out [service] {:op :scale-out :args {:service service}})
(defn page-human [service] {:op :page-human :args {:service service}})

(defn- service-of [operator] (get-in operator [:args :service]))

(defn- fix
  "A result that clears the page and heals the service."
  [state service note]
  (core/ok (-> state
               (assoc-in [:services service :health] :ok)
               (assoc :page nil))
           note))

(defn apply-op
  "Run one remedy. A remedy that does not match the root cause either does
  nothing (the page stays) or fails outright (rollback with nothing recent
  to roll back to)."
  [operator state]
  (let [s (service-of operator)
        svc (get-in state [:services s])
        cause (:root-cause svc)]
    (case (:op operator)
      :restart (let [state' (update-in state [:services s :restarts] inc)]
                 (if (= cause :memory-leak)
                   (fix state' s "restarted; heap reclaimed, page cleared")
                   (core/ok state (str "restarted " s "; still paging — not a leak"))))
      :rollback (if (< (get-in svc [:deploy :minutes-ago]) 30)
                  (if (contains? #{:bad-config :bad-code} cause)
                    (fix state s "rolled back the bad deploy; page cleared")
                    (core/ok state "rolled back; deploy was fine — still paging"))
                  (core/fail (str "last deploy to " s " is "
                                  (get-in svc [:deploy :minutes-ago])
                                  " min old — rollback window is 30")))
      :scale-out (if (= cause :capacity)
                   (fix state s "scaled +2 replicas; saturation gone")
                   (core/ok state "scaled +2; still paging — not capacity"))
      :page-human (fix state s "paged the on-call human; incident handed off")
      (core/fail (str "unknown operator " (:op operator))))))

(defn goal-met?
  "The page is cleared: every target service healthy and :page gone."
  [state goal]
  (and (nil? (:page state))
       (every? #(= :ok (get-in state [:services % :health])) (:target goal))))

(defn resolved?
  "Whether an apply-op result clears the incident: ok, the page gone, and
  every service healthy. (The page is gone when a fix lands, so the service
  cannot be read back off it.)"
  [result]
  (and (:ok result)
       (nil? (get-in result [:state :page]))
       (every? #(= :ok (get-in result [:state :services % :health]))
               (keys (get-in result [:state :services])))))

(defn runbook-proposer
  "The naive runbook: for the paged service, propose every remedy at equal
  priority. The tie is deliberate — deciding needs the root cause, and only
  the intuition engine can read those tea leaves."
  [state _goal]
  (let [s (get-in state [:page :service])
        recent-deploy? (< (get-in state [:services s :deploy :minutes-ago]) 30)]
    (cond-> []
      true (conj (core/proposal :restart {:service s} 1.0 "runbook/restart-first"))
      recent-deploy? (conj (core/proposal :rollback {:service s} 1.0 "runbook/rollback-if-deployed"))
      true (conj (core/proposal :scale-out {:service s} 1.0 "runbook/scale-if-saturated")))))

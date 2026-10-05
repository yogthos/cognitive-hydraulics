(ns hyd.agent
  "The decision cycle.

  One cycle: propose (rules) → detect impasse → apply the winner, or when
  stuck measure pressure and either subgoal (System 2) or go heuristic
  (System 1): a tie goes to ACT-R evaluation, a no-change to ACT-R
  generation. A heuristic pick that works is filed as a chunk. The engine is
  domain-agnostic: proposer, apply, goal-met? and intuition are injected."
  (:require [hyd.actr :as actr]
            [hyd.llm :as llm]
            [hyd.blocks :as blocks]
            [hyd.core :as core]
            [hyd.impasse :as impasse]
            [hyd.memory :as memory]
            [hyd.pressure :as pressure]
            [hyd.rules :as rules]))

(defn legal-moves
  "Every move that actually relocates a clear block onto a clear support
  (never onto itself, never to where it already sits)."
  [state]
  (let [clear (blocks/clear state)
        on (:on state)]
    (for [b (disj clear :table)
          to clear
          :when (and (not= to b)
                     (not= to (get on b)))]
      {:op :move :args {:b b :to to}})))

(defn blocks-proposer
  "The naive blocks-world rule book: every legal move at equal priority, so
  the symbolic layer ties and impasse handling does the interesting work."
  [state goal]
  (map #(core/proposal :move (:args %) 1.0 "legal-move")
       (legal-moves state)))

(defn goal-directed-proposer
  "A rule book that knows the goal: move each goal-named block onto its
  goal support when both are free. Solves without any impasse."
  [state goal]
  (let [clear (blocks/clear state)
        on (:on state)]
    (for [[b support] (:target goal)
          :when (and (contains? on b)
                     (not= support (get on b))
                     (contains? clear b)
                     (or (= support :table) (contains? clear support)))]
      (core/proposal :move {:b b :to support} 1.0 "goal-move"))))

(defn- metrics
  "Cognitive load of the current situation, for the pressure valve."
  [wm depth impasses proposals]
  {:depth depth
   :time-ms (* (count (:history wm)) 100)
   :impasses impasses
   :ambiguity (impasse/ambiguity proposals)})

(defn- apply-winner
  "Run the chosen operator through the domain, recording the transition."
  [domain proposal wm]
  (let [result ((:apply domain) (:op proposal) (:state wm))]
    (memory/record wm proposal result
                   (if (:ok result) (:state result) (:state wm)))))

(defn- last-applied
  "The operator most recently recorded in wm."
  [wm]
  (get-in wm [:history (dec (count (:history wm))) :op]))

(defn- fallback
  "System 1 over given candidates: intuition estimates, ACT-R selects.
  Returns the updated wm or nil."
  [domain intuition params wm candidates]
  (let [ctx {:state (:state wm) :counts (:counts wm)}
        resolution (actr/resolve intuition candidates ctx params)]
    (when-let [chosen (:chosen resolution)]
      (apply-winner domain {:op chosen :priority 0 :rule "actr"} wm))))

(defn- generate
  "System 1 when nothing was proposed: intuition generates candidates, then
  each is estimated and selected among. Returns the updated wm or nil."
  [domain intuition params wm]
  (let [ctx {:state (:state wm) :counts (:counts wm)}
        candidates (llm/propose intuition ctx)]
    (when (seq candidates)
      (fallback domain intuition params wm candidates))))

(defn- chunk-for
  "The chunk remembering a heuristic resolution that worked."
  [wm-before wm-after goal]
  (let [op (last-applied wm-after)]
    {:state (:state wm-before) :op (:op op) :args (:args op)
     :goal goal :utility 0.0}))

(defn solve
  "Run the decision cycle to the goal or the cycle bound.

  opts: :state :goal :proposer :apply :goal-met? :intuition :params
  :max-cycles.

  Returns {:solved? :final-state :cycles :chunks :trace}."
  [{:keys [state goal proposer apply goal-met? intuition params max-cycles]
    :or {params core/defaults}}]
  (let [max-cycles (or max-cycles (:max-cycles core/defaults))
        domain {:apply apply}]
    (loop [wm (memory/wm state)
           chunks []
           depth 0
           impasses 0
           cycle 0
           trace []]
      (cond
        (goal-met? (:state wm) goal)
        {:solved? true :final-state (:state wm) :cycles cycle
         :chunks chunks :trace trace}

        (>= cycle max-cycles)
        {:solved? false :final-state (:state wm) :cycles cycle
         :chunks chunks :trace trace}

        :else
        (let [proposals (proposer (:state wm) goal)
              imp (impasse/detect proposals)]
          (if (nil? imp)
            (let [wm' (apply-winner domain (first proposals) wm)]
              (recur wm' chunks depth impasses (inc cycle)
                     (conj trace {:cycle cycle
                                  :op (get-in (vec proposals) [0 :op :op])
                                  :args (get-in (vec proposals) [0 :op :args])
                                  :via :rule})))
            (let [m (metrics wm depth (inc impasses) (or (:candidates imp) proposals))
                  candidates (mapv :op (or (:candidates imp) []))]
              (cond
                ;; System 1: pressure too high for deliberation
                (pressure/fallback? m)
                (let [generated? (empty? candidates)
                      wm' (if generated?
                            (generate domain intuition params wm)
                            (fallback domain intuition params wm candidates))]
                  (if wm'
                    (let [op (last-applied wm')]
                      (recur wm'
                             (conj chunks (chunk-for wm wm' goal))
                             depth (inc impasses) (inc cycle)
                             (conj trace {:cycle cycle :op (:op op) :args (:args op)
                                          :via (if generated? :actr-generate :actr)})))
                    (recur wm chunks (inc depth) (inc impasses) (inc cycle)
                           (conj trace {:cycle cycle :via :subgoal}))))

                ;; System 2 continues: tie-break takes the first candidate.
                ;; The tie still costs: depth climbs, so a stubborn
                ;; oscillation eventually breaches the pressure threshold
                ;; and System 1 takes the tie over.
                (= :tie (:type imp))
                (let [cands (vec (:candidates imp))
                      wm' (apply-winner domain (first cands) wm)]
                  (recur wm' chunks (inc depth) (inc impasses) (inc cycle)
                         (conj trace {:cycle cycle
                                      :op (get-in cands [0 :op :op])
                                      :args (get-in cands [0 :op :args])
                                      :via :tie-break})))

                ;; no-change at low pressure: think harder (depth raises
                ;; pressure, so System 1 eventually fires)
                :else
                (recur wm chunks (inc depth) (inc impasses) (inc cycle)
                       (conj trace {:cycle cycle :via :subgoal}))))))))))

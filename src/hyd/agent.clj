(ns hyd.agent
  "The decision cycle.

  One cycle: gather preferences — the rules', learned chunks', and
  rejections of operators known to do nothing here — and decide (see
  hyd.impasse). A selection is applied. An impasse pushes a substate onto
  the goal stack and the pressure valve is read:

    below the threshold, System 2 deliberates in the substate: look-ahead
    through the domain's :simulate model (the agent's own model of its
    operators, which may be absent) evaluates the candidates and turns
    them into preferences. Unresolved, the substate stays, and the next
    impasse nests beneath it.

    at or above it, System 1 acts: ACT-R over intuition estimates of the
    candidates (or of operators the intuition generates, on a state
    no-change); when intuition says nothing, an indifferent pick.

  An applied operator that fails or changes nothing is an operator
  no-change: it is rejected in that state from then on. Progress — the
  state changes — pops the goal stack and relieves the pressure. A
  deliberate or heuristic resolution that made progress is filed as a
  chunk, and chunks fire as learned preferences in later decisions.

  The engine is domain-agnostic: proposer, apply, simulate, goal-met? and
  intuition are injected. Everything is pure; the seed is threaded."
  (:require [hyd.actr :as actr]
            [hyd.core :as core]
            [hyd.impasse :as impasse]
            [hyd.llm :as llm]
            [hyd.memory :as memory]
            [hyd.pressure :as pressure]))

(defn- progress?
  "Whether a result moved the world."
  [state result]
  (and (:ok result) (not= state (:state result))))

;; --- preferences ------------------------------------------------------------

(defn- learned
  "The chunk that fires here: the best recalled for this goal and a state
  this similar, whose operator is not rejected here. It proposes its
  operator and marks it best."
  [task run]
  (let [wm (:wm run)
        state (:state wm)
        c (first (remove #(memory/rejected? wm state (:op %))
                         (memory/recall (:store run) state (:goal task)
                                        (:chunk-threshold (:params task)))))]
    (if c
      [{:op (:op c) :priority 0.0 :rule "chunk"}
       (core/preference :best (:op c) "chunk")]
      [])))

(defn- rejections
  "Reject preferences for the operators known to do nothing here."
  [run]
  (let [state (:state (:wm run))]
    (keep (fn [[s op]] (when (= s state) (core/preference :reject op "no-change")))
          (:rejected (:wm run)))))

(defn- preferences
  [task run]
  (concat ((:proposer task) (:state (:wm run)) (:goal task))
          (learned task run)
          (rejections run)))

;; --- the run ----------------------------------------------------------------

(defn- note
  "Append a trace entry for this cycle."
  [run entry]
  (update run :trace conj (assoc entry :cycle (:cycle run))))

(defn- metrics
  "The load on the current substate."
  [task run prefs]
  {:depth (count (:stack run))
   :time-ms (* (:spent run) (:cycle-ms (:params task)))
   :impasses (:impasses run)
   :ambiguity (impasse/ambiguity prefs)})

(defn- apply-op
  "Apply op in the world. Progress pops the goal stack, resets the load and
  files a chunk when the resolution is learnable (utility given);
  otherwise it is an operator no-change and op is rejected here."
  [task run op entry utility]
  (let [wm (:wm run)
        state (:state wm)
        result ((:apply task) op state)
        wm' (memory/record wm op result)
        entry (assoc entry :op op)]
    (if (progress? state result)
      (let [c (when utility (memory/chunk state op (:goal task) utility))]
        (-> run
            (assoc :wm wm' :stack [] :spent 0 :impasses 0)
            (update :chunks #(if c (conj % c) %))
            (update :store #(if c (memory/remember % c) %))
            (note entry)))
      (-> run
          (assoc :wm (memory/reject wm' state op))
          (update :stack conj :operator-no-change)
          (update :impasses inc)
          (note (assoc entry :impasse :operator-no-change))))))

;; --- System 2: look-ahead ---------------------------------------------------

(defn- expand
  "One decision in the model from state: every candidate the rules leave
  (one, when they select), simulated. Returns the results."
  [task state]
  (let [d (impasse/decide ((:proposer task) state (:goal task)))]
    (mapv (fn [op] [state ((:simulate task) op state)]) (:candidates d))))

(defn- root
  "A candidate's first simulated step: rejected when it does nothing,
  :goal when it arrives, else open with its frontier."
  [task state op]
  (let [r ((:simulate task) op state)]
    (cond
      (not (progress? state r)) {:op op :status :reject}
      ((:goal-met? task) (:state r) (:goal task)) {:op op :status :goal}
      :else {:op op :status :open :frontier [(:state r)] :seen #{state (:state r)}})))

(defn- deepen
  "Search one level further below an open candidate. Returns the root
  updated and the simulations it cost."
  [task rt]
  (let [results (mapcat #(expand task %) (:frontier rt))
        fresh (distinct (keep (fn [[s r]] (when (and (progress? s r)
                                                     (not (contains? (:seen rt) (:state r))))
                                            (:state r)))
                              results))]
    [(cond
       (some #((:goal-met? task) % (:goal task)) fresh) (assoc rt :status :goal)
       (empty? fresh) (assoc rt :status :dead)
       :else (assoc rt :frontier fresh :seen (into (:seen rt) fresh)))
     (count results)]))

(defn- verdicts
  "Look-ahead's findings as preferences: the first shortest path to the
  goal is best (equally short ones are indifferent), dead ends are worst,
  operators that do nothing are rejected."
  [roots]
  (let [winner (first (filter #(= :goal (:status %)) roots))]
    (concat
     (when winner [(core/preference :best (:op winner) "lookahead")])
     (keep (fn [rt]
             (case (:status rt)
               :reject (core/preference :reject (:op rt) "lookahead")
               :dead (core/preference :worst (:op rt) "lookahead")
               nil))
           roots))))

(defn- lookahead
  "Evaluate candidates by breadth-first search in the model, one level at
  a time. Each level is a deeper substate and costs a cycle per simulated
  step; before descending, the valve is read with that load, and a
  breach abandons deliberation. Returns {:prefs :cost :escalate}, where
  :escalate is the breaching metrics or nil."
  [task cands state m]
  (let [params (:params task)
        roots (mapv #(root task state %) cands)]
    (loop [fuel (dec (:max-lookahead params))
           level 1
           roots roots
           cost (count cands)]
      (let [open? (some #(= :open (:status %)) roots)
            found? (some #(= :goal (:status %)) roots)
            deeper (assoc m
                          :depth (+ (:depth m) level)
                          :time-ms (+ (:time-ms m) (* cost (:cycle-ms params))))]
        (cond
          (or found? (not open?) (not (pos? fuel)))
          {:prefs (verdicts roots) :cost cost :escalate nil}

          (pressure/fallback? deeper params)
          {:prefs (verdicts roots) :cost cost :escalate deeper}

          :else
          (let [stepped (mapv #(if (= :open (:status %)) (deepen task %) [% 0]) roots)]
            (recur (dec fuel) (inc level) (mapv first stepped)
                   (+ cost (reduce + 0 (map second stepped))))))))))

;; --- System 1 ---------------------------------------------------------------

(defn- system-1
  "Heuristic resolution: ACT-R over the candidates' estimates, generating
  candidates when there are none; silent intuition picks indifferently."
  [task run cands entry]
  (let [wm (:wm run)
        state (:state wm)
        ctx {:state state :counts (:counts wm) :goal (:goal task)}
        generated? (empty? cands)
        cands (if generated?
                (remove #(memory/rejected? wm state %) (llm/propose (:intuition task) ctx))
                cands)
        r (when (seq cands)
            (actr/resolve (:intuition task) cands ctx (:params task) (:seed run)))]
    (cond
      r (apply-op task (assoc run :seed (:seed r)) (:chosen r)
                  (assoc entry :via (if generated? :actr-generate :actr))
                  (:utility r))
      (seq cands) (apply-op task (update run :seed actr/next-seed)
                            (nth (vec cands) (mod (:seed run) (count cands)))
                            (assoc entry :via :indifferent)
                            nil)
      :else (note run (assoc entry :via :stuck)))))

;; --- System 2 ---------------------------------------------------------------

(defn- system-2
  "Deliberation in the substate. With a model, look-ahead turns the
  candidates into preferences and decides again among them; a breach of
  the valve mid-search hands over to System 1. Without a model, or with
  nothing to evaluate, the substate stays unresolved."
  [task run cands m entry]
  (if (and (:simulate task) (seq cands))
    (let [la (lookahead task cands (:state (:wm run)) m)
          run (update run :spent + (:cost la))
          d (impasse/decide (concat (map (fn [o] {:op o :priority 0.0}) cands) (:prefs la)))]
      (cond
        (= :select (:type d))
        (apply-op task run (:op d) (assoc entry :via :lookahead)
                  (:goal-value (:params task)))

        (:escalate la)
        (system-1 task run (if (seq (:candidates d)) (:candidates d) cands)
                  (assoc entry :pressure (pressure/pressure (:escalate la) (:params task))))

        :else (note run (assoc entry :via :subgoal))))
    (note run (assoc entry :via :subgoal))))

;; --- the cycle --------------------------------------------------------------

(defn- on-impasse
  "Push a substate for the impasse and read the valve."
  [task run d prefs]
  (let [run (-> run (update :stack conj (:type d)) (update :impasses inc))
        m (metrics task run prefs)
        p (pressure/pressure m (:params task))
        entry {:impasse (:type d) :depth (count (:stack run)) :pressure p}]
    (if (pressure/fallback? m (:params task))
      (system-1 task run (:candidates d) entry)
      (system-2 task run (:candidates d) m entry))))

(defn- step
  "One decision cycle. A cycle that leaves the state where it was adds to
  the time spent in it."
  [task run]
  (let [prefs (preferences task run)
        d (impasse/decide prefs)
        chunked? (some #(and (= "chunk" (:rule %)) (= (:op d) (:op %))) prefs)
        run' (if (= :select (:type d))
               (apply-op task run (:op d)
                         {:via (if chunked? :chunk :rule) :depth (count (:stack run))}
                         nil)
               (on-impasse task run d prefs))]
    (-> (if (= (:state (:wm run)) (:state (:wm run')))
          (update run' :spent inc)
          run')
        (update :cycle inc))))

(defn- report
  [run solved?]
  {:solved? solved?
   :final-state (:state (:wm run))
   :cycles (:cycle run)
   :chunks (:chunks run)
   :store (:store run)
   :trace (:trace run)})

(defn solve
  "Run the decision cycle to the goal or the cycle bound.

  task: :state :goal :proposer :apply :goal-met? :intuition, and optionally
  :simulate (the agent's model of its operators, for look-ahead), :store
  (learned chunks), :params (over hyd.core/defaults), :max-cycles.

  Returns {:solved? :final-state :cycles :chunks (filed this run) :store
  (with them) :trace}. Each trace entry has :cycle :via (:rule :chunk
  :lookahead :actr :actr-generate :indifferent :subgoal :stuck), :op when
  one was applied, :impasse, :depth and :pressure when deliberation ran."
  [task]
  (let [params (core/params (:params task))
        task (assoc task :params params)
        max-cycles (or (:max-cycles task) (:max-cycles params))]
    (loop [fuel max-cycles
           run {:wm (memory/wm (:state task))
                :store (or (:store task) (memory/store))
                :chunks []
                :stack []
                :spent 0
                :impasses 0
                :seed (actr/seed (:seed params))
                :cycle 0
                :trace []}]
      (cond
        ((:goal-met? task) (:state (:wm run)) (:goal task)) (report run true)
        (not (pos? fuel)) (report run false)
        :else (recur (dec fuel) (step task run))))))

(ns hyd.agent-spec
  "The contract for hyd.agent: the decision cycle.

  Each cycle: preferences (the rules', learned chunks', and rejections of
  operators that did nothing here) → decide → apply the selection, or on
  an impasse push a substate and measure pressure:

    below the threshold — System 2 deliberates in the substate: look-ahead
      through the domain's :simulate model turns the candidates into
      preferences; unresolved, the substate stays and the next impasse
      nests deeper
    at or above it — System 1: ACT-R over intuition estimates (generated
      candidates on a state no-change), and when intuition is silent an
      indifferent pick

  Applying an operator that fails or changes nothing is an operator
  no-change: that operator is rejected in that state. Progress (the state
  changes) pops the goal stack and relieves the pressure. A deliberate or
  heuristic resolution that made progress is chunked, and solve consults
  chunks as learned best preferences.

  The laws run whole scenarios: the blocks world, and a counter."
  (:require [writ.spec :refer [spec ann law refine graph]]
            [hyd.blocks :as blocks]
            [hyd.core :as core]
            [hyd.llm :as llm]))

(spec hyd.agent)

;; --- vocabulary -------------------------------------------------------------

(refine Task [t {:state Any, :goal Any, :proposer Any, :apply Any, :goal-met? Any,
                 :intuition (Opt Any), :simulate (Opt Any), :store (Opt {:chunks (List Any)}),
                 :params (Opt (Map Keyword Any)), :max-cycles (Opt Nat)}]
  true)
(refine Report [r {:solved? Bool, :final-state Any, :cycles Nat, :chunks (List Any),
                   :store {:chunks (List Any)}, :trace (List Any)}]
  true)

(def quiet {:noise-s 0.0})

(def a->b {:op :move :args {:b :a :to :b}})
(def b->a {:op :move :args {:b :b :to :a}})

(def two-blocks
  {:state {:on {:a :table :b :table}}
   :goal {:target {:a :b}}
   :apply blocks/apply-op
   :goal-met? blocks/goal-met?
   :intuition (llm/->StubLLM {} nil)
   :params quiet})

(def knows-a->b (llm/->StubLLM {a->b {:p 0.9 :c 1.0}} nil))

(defn vias [out] (mapv :via (:trace out)))
(defn count-via [v out] (count (filter #{v} (vias out))))
(defn applied [out] (keep :op (:trace out)))
(defn close? [a b] (< (abs (- a b)) 1.0e-9))

;; the counter: two operators that both make progress, always tied, so
;; every step is an impasse
(defn bump [op state]
  (if (= :bump (:op op))
    (core/ok (update state :n + 1) "bumped")
    (core/fail "unknown")))
(defn bumps [_ _]
  [(core/proposal :bump {:hand :left} 1.0 "left")
   (core/proposal :bump {:hand :right} 1.0 "right")])
(def counter
  {:state {:n 0}
   :goal 3
   :proposer bumps
   :apply bump
   :goal-met? (fn [s g] (>= (:n s) g))
   :intuition (llm/->StubLLM {{:op :bump :args {:hand :left}} {:p 0.9 :c 1.0}} nil)
   :params quiet})

;; --- signature ---------------------------------------------------------------

(ann solve [Task -> Report])

(graph run
  {:states {:task Task, :report Report}
   :edges  {:task {[solve] #{:report}}}})

;; --- rules alone -------------------------------------------------------------

(law rules-alone-solve
  (let [out (solve (assoc two-blocks :proposer blocks/goal-directed-proposer))]
    (and (:solved? out)
         (= {:on {:a :b :b :table}} (:final-state out))
         (= [:rule] (vias out))
         (empty? (:chunks out)))))

;; the winner is the highest priority, wherever the rules listed it
(law clear-winner-is-applied
  (let [out (solve (assoc two-blocks
                          :proposer (fn [_ _] [(core/proposal :move {:b :b :to :a} 1.0 "low")
                                               (core/proposal :move {:b :a :to :b} 5.0 "high")])))]
    (and (:solved? out) (= [a->b] (applied out)) (= [:rule] (vias out)))))

;; partial params fill in from the defaults
(law partial-params
  (:solved? (solve (assoc two-blocks
                          :proposer blocks/naive-proposer
                          :intuition knows-a->b
                          :params {:noise-s 0.0}))))

(law no-params
  (:solved? (solve (-> two-blocks
                       (assoc :proposer blocks/goal-directed-proposer)
                       (dissoc :params)))))

;; --- the valve ---------------------------------------------------------------

;; no model to deliberate with: the substate nests until pressure opens
;; the valve, then ACT-R picks the goal move
(law ties-escalate-to-system-one
  (let [out (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b))]
    (and (:solved? out)
         (= [:subgoal :subgoal :actr] (vias out))
         (= [1 2 3] (mapv :depth (:trace out)))
         (= [a->b] (applied out)))))

;; ambiguity is read over every proposal, not just the tied ones:
;; a 2-way tie over 3 proposals is 0.5 ambiguous
(law ambiguity-reads-the-field
  (let [out (solve (assoc two-blocks
                          :proposer (fn [_ _] [(core/proposal :move {:b :a :to :b} 5.0 "x")
                                               (core/proposal :move {:b :b :to :a} 5.0 "y")
                                               (core/proposal :move {:b :a :to :table} 0.0 "z")])
                          :max-cycles 1))]
    (close? (+ (* 0.35 (/ 1.0 3)) (* 0.2 (/ 1.0 3)) (* 0.2 0.5))
            (:pressure (first (:trace out))))))

;; the caller's threshold is the threshold
(law threshold-is-params
  (= [:actr]
     (vias (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b
                         :params {:noise-s 0.0 :pressure-threshold 0.3})))))

;; progress relieves pressure: every step of the counter is an impasse, and
;; each one starts again at depth 1 instead of going straight to System 1
(law progress-relieves-pressure
  (let [out (solve counter)]
    (and (:solved? out)
         (= [:subgoal :subgoal :actr :subgoal :subgoal :actr :subgoal :subgoal :actr] (vias out))
         (= [1 2 3 1 2 3 1 2 3] (mapv :depth (:trace out))))))

;; --- System 2: look-ahead in the substate ------------------------------------

(law lookahead-resolves-ties
  (let [out (solve (assoc two-blocks :proposer blocks/naive-proposer :simulate blocks/apply-op))]
    (and (:solved? out)
         (= [:lookahead] (vias out))
         (= [a->b] (applied out)))))

;; deeper problems search deeper: c sits on a, so a needs two moves
(law lookahead-searches-deeper
  (let [out (solve {:state {:on {:a :table :b :table :c :a}}
                    :goal {:target {:a :b}}
                    :proposer blocks/naive-proposer
                    :apply blocks/apply-op
                    :simulate blocks/apply-op
                    :goal-met? blocks/goal-met?
                    :intuition (llm/->StubLLM {} nil)
                    :params quiet})]
    (and (:solved? out)
         (= 2 (count (applied out)))
         (every? #{:lookahead :rule} (vias out)))))

;; deliberation costs: four blocks tie twelve ways, a two-move goal finds
;; nothing one level down, and descending would breach the valve — so
;; System 1 takes the first step and look-ahead the second
(def four-blocks
  {:state {:on {:a :table :b :table :c :table :d :table}}
   :goal {:target {:a :b :b :c}}
   :proposer blocks/naive-proposer
   :apply blocks/apply-op
   :simulate blocks/apply-op
   :goal-met? blocks/goal-met?
   :intuition (llm/->StubLLM {{:op :move :args {:b :b :to :c}} {:p 0.9 :c 1.0}} nil)
   :params quiet})

(law search-breaches-the-valve
  (let [out (solve four-blocks)
        t (first (:trace out))]
    (and (:solved? out)
         (= [:actr :lookahead] (vias out))
         (= :tie (:impasse t))
         (<= 0.7 (:pressure t)))))

;; a search that runs out of levels without an answer leaves the substate
(law shallow-search-subgoals
  (= :subgoal
     (:via (first (:trace (solve (assoc-in four-blocks [:params :max-lookahead] 1)))))))

;; what the model says does nothing is rejected in the substate, never tried
(law model-rejects-in-the-substate
  (let [bad {:op :move :args {:b :c :to :zz}}
        out (solve {:state {:on {:a :table :b :table :c :a}}
                    :goal {:target {:a :b}}
                    :proposer (fn [s g] (cons (core/proposal :move {:b :c :to :zz} 1.0 "bad")
                                              (blocks/naive-proposer s g)))
                    :apply blocks/apply-op
                    :simulate blocks/apply-op
                    :goal-met? blocks/goal-met?
                    :intuition (llm/->StubLLM {} nil)
                    :params quiet})]
    (and (:solved? out) (not (some #{bad} (applied out))))))

;; nothing proposed, a model, but nothing to evaluate: the substate stays
(law model-without-candidates-subgoals
  (= :subgoal
     (:via (first (:trace (solve (assoc two-blocks :proposer (constantly [])
                                        :simulate blocks/apply-op :max-cycles 1)))))))

;; --- the taxonomy ------------------------------------------------------------

;; two rules each requiring an operator: a constraint failure, settled by
;; deliberation
(law constraint-failure-is-deliberated
  (let [out (solve (assoc two-blocks
                          :proposer (fn [_ _] [(core/preference :require a->b "r1")
                                               (core/preference :require b->a "r2")])
                          :simulate blocks/apply-op))]
    (and (:solved? out)
         (= :constraint-failure (:impasse (first (:trace out))))
         (= [a->b] (applied out)))))

(law conflict-is-deliberated
  (let [out (solve (assoc two-blocks
                          :proposer (fn [_ _] [(core/proposal :move {:b :a :to :b} 1.0 "x")
                                               (core/proposal :move {:b :b :to :a} 1.0 "y")
                                               (core/relative :better a->b b->a "r1")
                                               (core/relative :better b->a a->b "r2")])
                          :simulate blocks/apply-op))]
    (and (:solved? out)
         (= :conflict (:impasse (first (:trace out)))))))

;; an operator that fails is an operator no-change, rejected from then on:
;; the failing rule runs once, not until the cycle bound
(law operator-no-change-rejects
  (let [bad {:op :move :args {:b :a :to :zz}}
        out (solve (assoc two-blocks
                          :proposer (fn [_ _] [(core/proposal :move {:b :a :to :zz} 1.0 "bad")])
                          :max-cycles 10))]
    (and (= 1 (count (filter #{bad} (applied out))))
         (= :operator-no-change (:impasse (first (:trace out))))
         (= :state-no-change (:impasse (second (:trace out)))))))

;; a rejection holds in its own state only: in each new state the broken
;; rule gets one more try
(law rejection-is-per-state
  (let [bad {:op :bump :args {:hand :broken}}
        out (solve (assoc counter
                          :proposer (fn [s g] (cons (core/proposal :bump {:hand :broken} 2.0 "broken")
                                                    (bumps s g)))
                          :apply (fn [op s] (if (= bad op) (core/fail "broken") (bump op s)))))]
    (and (:solved? out)
         (= 3 (count (filter #{bad} (applied out)))))))

;; nothing proposed: intuition generates the operator
(law state-no-change-generates
  (let [out (solve (assoc two-blocks
                          :proposer (constantly [])
                          :intuition (llm/->StubLLM {a->b {:p 0.9 :c 1.0}} [a->b])))]
    (and (:solved? out)
         (= 1 (count-via :actr-generate out)))))

;; --- System 1 silent ---------------------------------------------------------

;; no estimates at all: an indifferent pick, never a spin
(law silent-intuition-picks-indifferently
  (let [out (solve (assoc two-blocks :proposer blocks/naive-proposer :max-cycles 30))]
    (and (pos? (count-via :indifferent out))
         (zero? (count-via :stuck out)))))

;; nothing to pick from and nothing generated: stuck, to the bound
(law nothing-at-all-is-stuck
  (let [out (solve (assoc two-blocks :proposer (constantly []) :max-cycles 7))]
    (and (not (:solved? out))
         (= 7 (:cycles out))
         (pos? (count-via :stuck out)))))

;; --- chunks ------------------------------------------------------------------

(law resolution-is-chunked
  (let [out (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b))
        c (first (:chunks out))]
    (and (= 1 (count (:chunks out)))
         (= a->b (:op c))
         (= {:on {:a :table :b :table}} (:state c))
         (= {:target {:a :b}} (:goal c))
         (close? (- (* 0.9 10.0) 1.0) (:utility c))
         (= (:chunks out) (:chunks (:store out))))))

;; a pick that does nothing is never chunked
(law failures-are-not-chunked
  (let [bad {:op :move :args {:b :a :to :zz}}
        out (solve (assoc two-blocks
                          :proposer (constantly [])
                          :intuition (llm/->StubLLM {bad {:p 0.9 :c 1.0}} [bad])
                          :max-cycles 8))]
    (and (not (:solved? out)) (empty? (:chunks out)))))

;; the second time, the chunk fires before any impasse: no LLM needed
(law chunks-are-recalled
  (let [first-run (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b))
        again (solve (assoc two-blocks :proposer blocks/naive-proposer
                            :store (:store first-run)))]
    (and (:solved? again)
         (= [:chunk] (vias again))
         (= [a->b] (applied again)))))

;; a chunk is a preference among preferences: a rule's require still wins
(law require-overrides-a-chunk
  (let [first-run (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b))
        again (solve (assoc two-blocks
                            :proposer (fn [s g] (cons (core/preference :require b->a "must")
                                                      (blocks/naive-proposer s g)))
                            :store (:store first-run)
                            :max-cycles 1))]
    (and (= [:rule] (vias again)) (= [b->a] (applied again)))))

;; a chunk is for its goal
(law chunks-keep-to-their-goal
  (let [first-run (solve (assoc two-blocks :proposer blocks/naive-proposer :intuition knows-a->b))
        other (solve (assoc two-blocks :proposer blocks/naive-proposer
                            :goal {:target {:b :a}}
                            :intuition (llm/->StubLLM {b->a {:p 0.9 :c 1.0}} nil)
                            :store (:store first-run)))]
    (and (:solved? other) (zero? (count-via :chunk other)))))

;; --- noise -------------------------------------------------------------------

;; a seed replays a noisy run
(law seed-replays
  (let [task (assoc two-blocks :proposer blocks/naive-proposer
                    :intuition (llm/->StubLLM {a->b {:p 0.5 :c 1.0} b->a {:p 0.45 :c 1.0}} nil)
                    :params {:noise-s 1.0 :seed 7})]
    (= (:trace (solve task)) (:trace (solve task)))))

;; and different seeds take different paths through a close call
(law noise-changes-paths
  (let [task (assoc two-blocks :proposer blocks/naive-proposer
                    :intuition (llm/->StubLLM {a->b {:p 0.5 :c 1.0} b->a {:p 0.45 :c 1.0}} nil))]
    (< 1 (count (distinct (map (fn [s] (first (applied (solve (assoc task :params {:noise-s 1.0 :seed s})))))
                               (range 1 30)))))))

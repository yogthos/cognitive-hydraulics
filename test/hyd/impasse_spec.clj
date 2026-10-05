(ns hyd.impasse-spec
  "The contract for hyd.impasse: Soar's decision procedure.

  Rules emit preferences about operators: acceptable (with a numeric
  priority), reject, prohibit, require, best, worst, better and worse
  (relative to :than). decide reads them in Soar's order — require, then
  the acceptable set minus reject/prohibit, then better/worse, best,
  worst, numeric — and either selects one operator or names the impasse:

    :constraint-failure  more than one operator required, or a required
                         one also rejected or prohibited
    :state-no-change     nothing acceptable survives
    :conflict            two candidates each better than the other
    :tie                 several candidates the preferences cannot split

  (The fifth Soar impasse, operator no-change, is a property of applying
  an operator, not of the preferences; the agent detects it.)

  The decision depends on what was preferred, never on the order the rules
  fired in, and a preference stated twice is stated once."
  (:require [writ.spec :refer [spec ann law refine graph example]]))

(spec hyd.impasse)

;; --- vocabulary -------------------------------------------------------------

(def KINDS #{:acceptable :reject :prohibit :require :best :worst :better :worse})

(refine Kind [k Keyword] (contains? KINDS k))

;; priorities are rule-author numbers, not float extremes
(refine Prio [x Double] (<= (abs x) 1000.0))

;; a preference; :pref absent reads as :acceptable, :priority absent as 0.0
(refine Pref [p {:op Keyword, :pref (Opt Kind), :priority (Opt Prio), :than (Opt Keyword)}] true)

;; a plain proposal: acceptable at a priority
(refine Proposal [p {:op Keyword, :priority Prio}] true)

(refine Decision [d {:type Keyword, :op (Opt Any), :candidates (List Any)}] true)

(defn kind-of [p] (or (:pref p) :acceptable))

(defn marked? [k op ps]
  (boolean (some (fn [p] (and (= k (kind-of p)) (= op (:op p)))) ps)))

(defn live? [op ps]
  (and (marked? :acceptable op ps)
       (not (marked? :reject op ps))
       (not (marked? :prohibit op ps))))

(defn prio [op ps]
  (reduce max -1.0e300
          (map (fn [p] (or (:priority p) 0.0))
               (filter (fn [p] (and (= :acceptable (kind-of p)) (= op (:op p)))) ps))))

(defn top-ops
  "The distinct operators at the top priority of plain proposals."
  [ps]
  (let [ops (distinct (map :op ps))
        mx (reduce max -1.0e300 (map (fn [o] (prio o ps)) ops))]
    (filter (fn [o] (= mx (prio o ps))) ops)))

(defn same-decision?
  "Two decisions agree: same type, same selection, same candidate set."
  [a b]
  (and (= (:type a) (:type b))
       (= (:op a) (:op b))
       (= (set (:candidates a)) (set (:candidates b)))))

(defn shaped?
  "What each kind of decision must carry."
  [d]
  (case (:type d)
    :select (= [(:op d)] (vec (:candidates d)))
    :tie (and (nil? (:op d)) (<= 2 (count (distinct (:candidates d)))))
    :conflict (and (nil? (:op d)) (<= 2 (count (distinct (:candidates d)))))
    :constraint-failure (and (nil? (:op d)) (<= 1 (count (distinct (:candidates d)))))
    :state-no-change (and (nil? (:op d)) (empty? (:candidates d)))
    false))

(refine Selected [d Decision] (and (= :select (:type d)) (shaped? d)))
(refine Impasse [d Decision] (and (not= :select (:type d)) (shaped? d)))

;; --- signatures --------------------------------------------------------------

(ann decide [(List Pref) -> Decision])
(ann candidates [(List Pref) -> (List Any)])
(ann ambiguity [(List Pref) -> Double])

;; preferences go in; out comes a selection or a well-formed impasse
(graph decision
  {:states {:prefs (List Pref), :selected Selected, :impasse Impasse}
   :edges  {:prefs {[decide] #{:selected :impasse}}}})

;; --- the candidate set -------------------------------------------------------

;; the live operators, each once, in the order first proposed
(law candidates-model
  (forall [ps (List Pref)]
    (= (vec (candidates ps))
       (vec (filter (fn [o] (live? o ps))
                    (distinct (map :op (filter (fn [p] (= :acceptable (kind-of p))) ps))))))))

;; --- order and repetition do not matter --------------------------------------

(law order-independent
  (forall [ps (List Pref)]
    (same-decision? (decide ps) (decide (reverse ps)))))
(law restating-changes-nothing
  (forall [ps (List Pref)]
    (=> (seq ps)
        (same-decision? (decide ps) (decide (cons (first ps) ps))))))

;; --- the numeric stage: plain proposals --------------------------------------

;; the highest priority wins wherever it sits in the list
(law max-priority-wins
  (forall [a Keyword, b Keyword, pa Prio, pb Prio]
    (=> (and (not= a b) (> pa pb))
        (and (= a (:op (decide [{:op b :priority pb} {:op a :priority pa}])))
             (= a (:op (decide [{:op a :priority pa} {:op b :priority pb}])))))))

;; plain proposals: a selection exactly when one operator holds the top
;; priority, otherwise a tie among exactly the top operators
(law numeric-stage
  (forall [ps (List Proposal)]
    (=> (seq ps)
        (let [d (decide ps)
              top (top-ops ps)]
          (and (= (set top) (set (:candidates d)))
               (= (:type d) (if (= 1 (count top)) :select :tie)))))))

(law same-operator-twice-is-no-tie
  (forall [a Keyword, p Prio]
    (= {:type :select :op a :candidates [a]}
       (decide [{:op a :priority p :rule "r1"} {:op a :priority p :rule "r2"}]))))

;; --- state no-change ---------------------------------------------------------

(example decide [[]] {:type :state-no-change :op nil :candidates []})

(law everything-rejected-is-state-no-change
  (forall [ps (List Proposal)]
    (= :state-no-change
       (:type (decide (concat ps (map (fn [p] {:op (:op p) :pref :reject}) ps)))))))

;; a rejected or prohibited operator is never selected, and is a candidate
;; only of the constraint failure its own require causes
(law reject-excludes
  (forall [ps (List Pref), a Keyword]
    (let [d (decide (cons {:op a :pref :reject} ps))]
      (and (not= a (:op d))
           (=> (some #{a} (:candidates d))
               (and (= :constraint-failure (:type d)) (marked? :require a ps)))))))

(law prohibit-excludes
  (forall [ps (List Pref), a Keyword]
    (let [d (decide (cons {:op a :pref :prohibit} ps))]
      (and (not= a (:op d))
           (=> (some #{a} (:candidates d))
               (and (= :constraint-failure (:type d)) (marked? :require a ps)))))))

;; a required operator that is also rejected fails the constraint
(law required-and-rejected-fails
  (forall [a Keyword, p Prio]
    (= {:type :constraint-failure :op nil :candidates [a]}
       (decide [{:op a :priority p} {:op a :pref :require} {:op a :pref :reject}]))))

;; --- require and constraint failure ------------------------------------------

(law require-wins-over-priority
  (forall [a Keyword, b Keyword, pa Prio, pb Prio]
    (=> (not= a b)
        (= a (:op (decide [{:op b :priority pb}
                           {:op a :priority pa}
                           {:op a :pref :require}]))))))

(law two-requires-fail
  (forall [a Keyword, b Keyword]
    (=> (not= a b)
        (let [d (decide [{:op a :pref :require} {:op b :pref :require}
                         {:op a :priority 1.0} {:op b :priority 1.0}])]
          (and (= :constraint-failure (:type d))
               (= #{a b} (set (:candidates d))))))))

(law required-and-prohibited-fails
  (forall [a Keyword]
    (= :constraint-failure
       (:type (decide [{:op a :priority 1.0} {:op a :pref :require} {:op a :pref :prohibit}])))))

;; --- better, worse, conflict -------------------------------------------------

(law better-breaks-a-tie
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= a (:op (decide [{:op a :priority p} {:op b :priority p}
                           {:op a :pref :better :than b}]))))))

(law worse-breaks-a-tie
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= a (:op (decide [{:op a :priority p} {:op b :priority p}
                           {:op b :pref :worse :than a}]))))))

(law mutual-better-is-conflict
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (let [d (decide [{:op a :priority p} {:op b :priority p}
                         {:op a :pref :better :than b} {:op b :pref :better :than a}])]
          (and (= :conflict (:type d))
               (= #{a b} (set (:candidates d))))))))

;; an operator better than itself says nothing
(law self-preference-is-ignored
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= :tie (:type (decide [{:op a :priority p} {:op b :priority p}
                                {:op a :pref :better :than a}]))))))

;; --- best and worst ----------------------------------------------------------

;; best is read before the numbers: a learned best beats a higher priority
(law best-beats-priority
  (forall [a Keyword, b Keyword, pa Prio, pb Prio]
    (=> (not= a b)
        (= a (:op (decide [{:op a :priority pa} {:op b :priority pb}
                           {:op a :pref :best}]))))))

(law worst-steps-aside
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= b (:op (decide [{:op a :priority p} {:op b :priority p}
                           {:op a :pref :worst}]))))))

;; when everything is worst, worst decides nothing
(law all-worst-still-ties
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= :tie (:type (decide [{:op a :priority p} {:op b :priority p}
                                {:op a :pref :worst} {:op b :pref :worst}]))))))

;; --- ambiguity ---------------------------------------------------------------

(example ambiguity [[]] 1.0)
(example ambiguity [[{:op :a :priority 1.0}]] 0.0)

(law ambiguity-bounded
  (forall [ps (List Pref)]
    (let [x (ambiguity ps)] (and (<= 0.0 x) (<= x 1.0)))))

;; every live candidate at one priority: fully ambiguous
(law all-equal-is-ambiguous
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= 1.0 (ambiguity [{:op a :priority p} {:op b :priority p}])))))

;; a clear winner far above the rest: no ambiguity
(law clear-winner-is-unambiguous
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= 0.0 (ambiguity [{:op a :priority (+ p 10.0)} {:op b :priority p}])))))

;; contenders (within 10% of the range below the top) beyond the first,
;; over candidates beyond the first
(law ambiguity-counts-contenders
  (= 0.5 (ambiguity [{:op :a :priority 5.0} {:op :b :priority 4.95} {:op :c :priority 4.0}])))

;; ambiguity reads the live field: a rejected rival is no rival
(law rejected-rivals-do-not-count
  (forall [a Keyword, b Keyword, p Prio]
    (=> (not= a b)
        (= 0.0 (ambiguity [{:op a :priority p} {:op b :priority p} {:op b :pref :reject}])))))

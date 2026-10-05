(ns hyd.impasse
  "Soar's decision procedure.

  Rules do not pick operators; they state preferences about them:

    :acceptable  a candidate, at a numeric :priority (the default kind)
    :reject      not this one          :prohibit  never this one
    :require     this one, and only this one
    :best        above every other     :worst     below every other
    :better      above :than           :worse     below :than

  decide reads them in Soar's order and either selects one operator or
  names the impasse the preferences leave:

    :constraint-failure  several operators required, or a required one
                         also rejected or prohibited
    :state-no-change     nothing acceptable survives
    :conflict            candidates each better than the other
    :tie                 candidates nothing tells apart

  The fifth impasse, operator no-change, belongs to application, not to
  preferences: the agent detects it when a selected operator fails or
  changes nothing. The decision never depends on the order rules fired in,
  and stating a preference twice states it once."
  (:require [hyd.core :as core]))

(defn- kind
  "A preference's kind; a bare proposal is acceptable."
  [p]
  (or (:pref p) :acceptable))

(defn- ops-of
  "The distinct operators carrying preference k."
  [k ps]
  (distinct (map :op (filter #(= k (kind %)) ps))))

(defn- marked
  "The set of operators carrying preference k."
  [k ps]
  (set (ops-of k ps)))

(defn- priority-of
  "An operator's priority: the highest any acceptable preference gives it."
  [op ps]
  (reduce max -1.0e300
          (map #(or (:priority %) 0.0)
               (filter #(and (= :acceptable (kind %)) (= op (:op %))) ps))))

(defn candidates
  "The live operators: acceptable, and neither rejected nor prohibited.
  Distinct, in the order first proposed."
  [ps]
  (let [out (into (marked :reject ps) (marked :prohibit ps))]
    (remove #(contains? out %) (ops-of :acceptable ps))))

(defn- relations
  "better/worse as [winner loser] pairs among the candidates."
  [ps cands]
  (let [in? (set cands)]
    (filter (fn [[w l]] (and (in? w) (in? l) (not= w l)))
            (map #(if (= :better (kind %)) [(:op %) (:than %)] [(:than %) (:op %)])
                 (filter #(contains? #{:better :worse} (kind %)) ps)))))

(defn- impasse
  [type cands]
  {:type type :op nil :candidates (vec cands)})

(defn- selection
  [op]
  {:type :select :op op :candidates [op]})

(defn- by-priority
  "The numeric stage: the top-priority candidates."
  [ps cands]
  (let [mx (reduce max -1.0e300 (map #(priority-of % ps) cands))]
    (filter #(= mx (priority-of % ps)) cands)))

(defn- settle
  "One candidate is a selection; more are a tie."
  [cands]
  (if (= 1 (count cands))
    (selection (first cands))
    (impasse :tie cands)))

(defn- prefer
  "best, then worst, then the numbers, over undominated candidates."
  [ps cands]
  (let [best (marked :best ps)
        worst (marked :worst ps)
        bests (filter #(contains? best %) cands)
        cands (if (seq bests) bests cands)
        unworst (remove #(contains? worst %) cands)
        cands (if (seq unworst) unworst cands)]
    (settle (by-priority ps cands))))

(defn- dominance
  "Apply better/worse: a mutual pair is a conflict; otherwise drop every
  candidate something else is better than."
  [ps cands]
  (let [rel (relations ps cands)
        pairs (set rel)
        mutual (distinct (mapcat identity (filter (fn [[w l]] (contains? pairs [l w])) rel)))
        losers (set (map second rel))]
    (if (seq mutual)
      (impasse :conflict mutual)
      (prefer ps (remove #(contains? losers %) cands)))))

(defn decide
  "Select an operator from preferences, or name the impasse. Returns
  {:type :select|:tie|:conflict|:constraint-failure|:state-no-change
   :op selected-or-nil :candidates [...]}."
  [ps]
  (let [required (ops-of :require ps)
        out (into (marked :reject ps) (marked :prohibit ps))
        cands (candidates ps)]
    (cond
      (or (< 1 (count required))
          (some #(contains? out %) required))
      (impasse :constraint-failure required)

      (= 1 (count required)) (selection (first required))

      (empty? cands) (impasse :state-no-change [])

      :else (dominance ps cands))))

(defn ambiguity
  "How undecided the live candidates are by priority: 0 for a clear winner,
  1 when all are equal or none survive. Contenders sit within 10% of the
  priority range below the top; the score is the contenders beyond the
  first over the candidates beyond the first."
  [ps]
  (let [cands (candidates ps)
        n (count cands)]
    (cond
      (zero? n) 1.0
      (= 1 n) 0.0
      :else (let [prios (map #(priority-of % ps) cands)
                  mx (reduce max prios)
                  mn (reduce min prios)
                  cutoff (- mx (* 0.1 (- mx mn)))
                  contenders (count (filter #(>= % cutoff) prios))]
              (/ (double (dec contenders)) (dec n))))))

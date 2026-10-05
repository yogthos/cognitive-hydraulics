(ns hyd.memory
  "Working memory and the chunk store.

  Working memory is the agent's short-term record: every transition, how
  often each operator has run (the tabu counts, keyed by the whole
  operator), and which operators did nothing in which state — an operator
  no-change — so they are rejected there from then on. All pure — the
  agent threads it through the cycle.

  Chunks are what learning leaves behind: the state, the operator that
  resolved an impasse there, the goal it served, and the utility it scored.
  A store is a plain map of chunks; recall is similarity over the states'
  leaf facts. Persistence lives outside the pure core (hyd.persist)."
  (:require [clojure.set :as set]))

(defn wm
  "Fresh working memory over an initial state."
  [state]
  {:state state :history [] :counts {} :rejected #{}})

(defn record
  "Record one transition: the operator and its result. A successful result
  moves working memory to its state; a failure leaves the state as it was.
  Counts key by the whole operator — the arguments are the action."
  [wm op result]
  (-> wm
      (update :history conj {:op op :result result})
      (update :counts update op (fnil inc 0))
      (assoc :state (if (:ok result) (:state result) (:state wm)))))

(defn reject
  "Remember that op did nothing in state (an operator no-change)."
  [wm state op]
  (update wm :rejected conj [state op]))

(defn rejected?
  "Whether op is known to do nothing in state."
  [wm state op]
  (contains? (:rejected wm) [state op]))

;; --- chunks -----------------------------------------------------------------

(defn chunk
  "A chunk: in this state, for this goal, this operator worked, scoring
  this utility. op is the whole operator map."
  [state op goal utility]
  {:state state :op op :goal goal :utility utility})

(defn store
  "An empty chunk store."
  []
  {:chunks []})

(defn- same-situation?
  [a b]
  (and (= (:state a) (:state b)) (= (:op a) (:op b)) (= (:goal a) (:goal b))))

(defn remember
  "File a chunk. One chunk per (state, op, goal): filing it again keeps
  the better utility."
  [store c]
  (if (some #(same-situation? % c) (:chunks store))
    (update store :chunks
            (fn [cs] (mapv #(if (same-situation? % c)
                              (assoc % :utility (max (:utility %) (:utility c)))
                              %)
                           cs)))
    (update store :chunks (fnil conj []) c)))

(defn- leaves
  "A value's leaf facts as [path value] pairs, maps walked to a fixed
  depth (an empty map states no fact); anything else is a leaf."
  [fuel path x]
  (if (and (pos? fuel) (map? x))
    (mapcat (fn [[k v]] (leaves (dec fuel) (conj path k) v)) x)
    [[path x]]))

(defn similarity
  "Overlap of two states' leaf facts, 0 to 1 (Jaccard); 1 for equal states."
  [a b]
  (let [fa (set (leaves 8 [] a))
        fb (set (leaves 8 [] b))
        n (count (set/union fa fb))]
    (if (zero? n)
      1.0
      (/ (double (count (set/intersection fa fb))) n))))

(defn recall
  "The chunks for this goal whose state is at least threshold-similar to
  state: most similar first, then highest utility."
  [store state goal threshold]
  (->> (:chunks store)
       (filter #(= goal (:goal %)))
       (map (fn [c] [(similarity state (:state c)) c]))
       (filter (fn [[s _]] (>= s threshold)))
       (sort-by (fn [[s c]] [(- s) (- (:utility c))]))
       (map second)))

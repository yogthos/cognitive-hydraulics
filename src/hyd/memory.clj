(ns hyd.memory
  "Working memory and the chunk store.

  Working memory is the agent's short-term record: every transition, how
  often each operator has run (the tabu counts), and whether the recent
  window is a loop. All pure — the agent threads it through the cycle.

  Chunks are what learning leaves behind: the state, the operator that
  worked, the goal it served, and the utility it scored. A store is an atom
  of chunks; recall is similarity on state keys. Durability is plain EDN."
  (:require [clojure.java.io :as io]
            [hyd.core :as core]))

(defn wm
  "Fresh working memory over an initial state."
  [state]
  {:state state :history [] :counts {}})

(defn record
  "Record one transition: the proposal, its result, and the next state.
  Counts key by the whole operator — the arguments are the action, and the
  tabu penalty in actr/select looks ops up by exactly this key."
  [wm proposal result state]
  (-> wm
      (update :history conj {:op (:op proposal) :result result})
      (update :counts update (:op proposal) (fnil inc 0))
      (assoc :state state)))

(defn failed-operators
  "Operators that failed in the last 20 transitions."
  [wm]
  (->> (take-last 20 (:history wm))
       (filter #(not (:ok (:result %))))
       (map #(get-in % [:op :op]))))

(defn looping?
  "True when the same operator failed three or more times recently."
  [wm]
  (->> (frequencies (failed-operators wm))
       (some #(>= (val %) 3))
       boolean))

;; --- chunks -----------------------------------------------------------------

(defn store
  "An empty chunk store."
  []
  {:chunks []})

(defn remember
  "File a chunk: what state, which operator worked, for what goal, at what
  utility."
  [store {:keys [state op goal utility]}]
  (update store :chunks conj {:state state :op op :goal goal :utility utility}))

(defn- similarity
  "Overlap of state keys between two states, 0 to 1."
  [a b]
  (let [ka (set (keys a)) kb (set (keys b))]
    (if (and (seq ka) (seq kb))
      (/ (count (clojure.set/intersection ka kb))
         (count (clojure.set/union ka kb)))
      0.0)))

(defn recall
  "The chunks most similar to the state, best first."
  [store state & [n]]
  (->> (:chunks store)
       (sort-by #(similarity state (:state %)) >)
       (take (or n 3))))

(defn save!
  "Write the store to an EDN file."
  [store path]
  (spit path (pr-str store)))

(defn load-store
  "Read a store from an EDN file; empty when absent."
  [path]
  (if (.exists (io/file path))
    (read-string (slurp path))
    (store)))

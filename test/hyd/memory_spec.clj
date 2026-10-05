(ns hyd.memory-spec
  "The contract for hyd.memory: working memory and the chunk store.

  Working memory records transitions, counts each operator by its whole
  map (the tabu counts), and remembers which operators did nothing in which
  state (operator no-change), so they are rejected there from then on.

  A chunk is {:state :op :goal :utility}, :op the whole operator. The store
  keeps one chunk per (state, op, goal), at its best utility. Similarity is
  overlap of the states' leaf facts — [path value] pairs — so two states
  with the same keys but different contents are not the same situation.
  Recall returns chunks for the same goal at or above a similarity
  threshold, most similar first, then highest utility."
  (:require [writ.spec :refer [spec ann law refine graph example]]))

(spec hyd.memory)

;; --- vocabulary -------------------------------------------------------------

(refine Unit [x Double] (and (<= 0.0 x) (<= x 1.0)))
(refine Op [o {:op Keyword, :args (Map Keyword Keyword)}] true)
(refine State [s (Map Keyword (Map Keyword Keyword))] true)
(refine Chunk [c {:state State, :op Op, :goal Keyword, :utility Double}] true)
(refine Store [s {:chunks (List Chunk)}] true)
;; a success carries the next state; a failure need not
(refine Result [r {:ok Bool, :state (Opt State)}] (or (not (:ok r)) (some? (:state r))))
(refine WM [w {:state State, :history (Vec Any), :counts (Map Any Nat), :rejected (Set Any)}] true)

(defn facts
  "A state's leaf facts, two levels deep, as the spec counts them."
  [s]
  (set (for [[k v] s, [k2 v2] v] [[k k2] v2])))

(defn jaccard [a b]
  (let [fa (facts a) fb (facts b)
        n (count (clojure.set/union fa fb))]
    (if (zero? n)
      1.0
      (/ (double (count (clojure.set/intersection fa fb))) n))))

(defn ordered? [cs state]
  (every? (fn [[x y]]
            (let [sx (jaccard state (:state x)) sy (jaccard state (:state y))]
              (or (> sx sy) (and (= sx sy) (>= (:utility x) (:utility y))))))
          (map vector cs (rest cs))))

(refine Filed [s Store] (seq (:chunks s)))

;; --- signatures --------------------------------------------------------------

(ann wm [Any -> WM])
(ann record [WM Op Result -> WM])
(ann reject [WM Any Op -> WM])
(ann rejected? [WM Any Op -> Bool])
(ann chunk [State Op Keyword Double -> Chunk])
(ann store [-> Store])
(ann remember [Store Chunk -> Store])
(ann similarity [State State -> Unit])
(ann recall [Store State Keyword Unit -> (List Chunk)])

;; experience fills the store; recall reads it back
(graph learning
  {:states {:store Store, :filed Filed}
   :edges  {:store {[remember Chunk] #{:filed}}
            :filed {[remember Chunk] #{:filed}}}})

;; --- working memory ----------------------------------------------------------

(law record-counts-whole-operator
  (forall [w WM, o Op, r Result]
    (= (inc (get (:counts w) o 0)) (get (:counts (record w o r)) o))))

(law record-appends-history
  (forall [w WM, o Op, r Result]
    (and (= (inc (count (:history w))) (count (:history (record w o r))))
         (= {:op o :result r} (last (:history (record w o r)))))))

(law success-advances-state
  (forall [w WM, o Op, s State]
    (= s (:state (record w o {:ok true :state s})))))

(law failure-keeps-state
  (forall [w WM, o Op]
    (= (:state w) (:state (record w o {:ok false :error "no"})))))

(law fresh-wm
  (forall [s State]
    (= {:state s :history [] :counts {} :rejected #{}} (wm s))))

;; operator no-change: rejected in that state, and only there
(law rejection-is-remembered
  (forall [w WM, s State, o Op]
    (rejected? (reject w s o) s o)))

(law fresh-rejects-nothing
  (forall [s State, t State, o Op]
    (not (rejected? (wm s) t o))))

;; exactly the (state, operator) pair rejected, nothing else
(law rejection-is-exact
  (forall [s State, t State, o Op, p Op, x State]
    (= (rejected? (reject (wm x) s o) t p)
       (and (= s t) (= o p)))))

(law rejection-is-exact-at-the-pair
  (forall [s State, o Op, x State]
    (rejected? (reject (wm x) s o) s o)))

;; --- chunks ------------------------------------------------------------------

(law empty-store (= {:chunks []} (store)))

;; one schema: the whole operator survives filing
(law chunk-keeps-operator
  (forall [s State, o Op, g Keyword, u Double]
    (= [{:state s :op o :goal g :utility u}]
       (vec (:chunks (remember (store) (chunk s o g u)))))))

(law remember-dedupes-at-best-utility
  (forall [s State, o Op, g Keyword, u Double, v Double]
    (= [(chunk s o g (max u v))]
       (vec (:chunks (remember (remember (store) (chunk s o g u)) (chunk s o g v)))))))

(law remember-keeps-distinct
  (forall [st Store, c Chunk]
    (=> (not-any? (fn [x] (and (= (:state x) (:state c)) (= (:op x) (:op c)) (= (:goal x) (:goal c))))
                  (:chunks st))
        (= (inc (count (:chunks st))) (count (:chunks (remember st c)))))))

(law remember-idempotent
  (forall [st Store, c Chunk]
    (= (remember st c) (remember (remember st c) c))))

;; a chunk for another state, or another goal, is another chunk
(law other-state-other-chunk
  (forall [s State, t State, o Op, g Keyword, u Double]
    (=> (not= s t)
        (= 2 (count (:chunks (remember (remember (store) (chunk s o g u)) (chunk t o g u))))))))
(law other-goal-other-chunk
  (forall [s State, o Op, g Keyword, h Keyword, u Double]
    (=> (not= g h)
        (= 2 (count (:chunks (remember (remember (store) (chunk s o g u)) (chunk s o h u))))))))

;; --- similarity --------------------------------------------------------------

(law similarity-model
  (forall [a State, b State]
    (= (similarity a b) (jaccard a b))))

(law similarity-reflexive (forall [a State] (= 1.0 (similarity a a))))
(law similarity-symmetric (forall [a State, b State] (= (similarity a b) (similarity b a))))

;; same keys, different contents: not the same situation
(law contents-matter
  (= (/ 1.0 3) (similarity {:on {:a :b :c :table}} {:on {:a :table :c :table}})))

;; --- recall ------------------------------------------------------------------

(law recall-same-goal-over-threshold
  (forall [st Store, s State, g Keyword, t Unit]
    (every? (fn [c] (and (= g (:goal c)) (>= (jaccard s (:state c)) t)))
            (recall st s g t))))

(law recall-misses-nothing
  (forall [st Store, s State, g Keyword, t Unit]
    (= (count (recall st s g t))
       (count (filter (fn [c] (and (= g (:goal c)) (>= (jaccard s (:state c)) t)))
                      (:chunks st))))))

(law recall-best-first
  (forall [st Store, s State, g Keyword, t Unit]
    (ordered? (recall st s g t) s)))

(law recall-exact
  (forall [s State, o Op, g Keyword]
    (= [(chunk s o g 1.0)]
       (vec (recall (remember (store) (chunk s o g 1.0)) s g 1.0)))))

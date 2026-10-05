(ns hyd.test-runner
  "Test runner. Each namespace runs in its own jolt process — not for speed,
  but because loading a third test namespace into one jolt process trips a
  runtime bug (a var resolves to a keyword mid-load, CCE inside perfectly
  good code). Sharding sidesteps it.

    jolt -M:test                 every namespace, one process each
    jolt -M:test --serial NS...  these namespaces in this process
  "
  (:require [clojure.java.shell :as sh]
            [clojure.string :as str]
            [clojure.test :as t]))

(def test-namespaces
  '[hyd.core-test
    hyd.impasse-test
    hyd.pressure-test
    hyd.actr-test
    hyd.memory-test
    hyd.rules-test
    hyd.blocks-test
    hyd.agent-test])

(defn- run-here
  "Run namespaces in this process. Returns the merged counters."
  [nss]
  (reduce (fn [acc ns]
            (require ns)
            (merge-with + acc (t/run-tests ns)))
          {:test 0 :pass 0 :fail 0 :error 0}
          nss))

(defn- run-child
  "Run one namespace in its own jolt process. Returns [exit out]."
  [ns]
  (let [{:keys [out exit]} (sh/sh "jolt" "-M:test" "--serial" (str ns))]
    [exit out]))

(defn -main
  [& args]
  (if (= (first args) "--serial")
    (let [{:keys [test pass fail error]} (run-here (map symbol (rest args)))]
      (println (str "\n" test " tests, " (+ pass fail error) " assertions, "
                   fail " failures, " error " errors."))
      (when (pos? (+ fail error))
        (System/exit 1)))
    (let [results (doall (for [ns test-namespaces]
                           (let [[exit out] (run-child ns)]
                             (print out)
                             [exit out])))
          failures (filter #(pos? (first %)) results)]
      (when (seq failures)
        (System/exit 1))
      (println "\nall namespaces green."))))

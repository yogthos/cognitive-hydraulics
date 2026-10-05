(ns ex.test-runner
  "Process-per-namespace runner, same shape as the library's: a third test
  namespace loaded into one jolt process trips a jolt runtime bug, so each
  namespace gets its own process.

    jolt -M:test            every namespace, one process each
    jolt -M:test --serial NS  these namespaces in this process
  "
  (:require [clojure.java.shell :as sh]
            [clojure.test :as t]))

(def test-namespaces
  '[ex.incident.world-test
    ex.incident.openai-test
    ex.incident.deepseek-test
    ex.incident.lev-test
    ex.incident.main-test])

(defn- run-here
  [nss]
  (reduce (fn [acc ns]
            (require ns)
            (merge-with + acc (t/run-tests ns)))
          {:test 0 :pass 0 :fail 0 :error 0}
          nss))

(defn -main
  [& args]
  (if (= (first args) "--serial")
    (let [{:keys [test pass fail error]} (run-here (map symbol (rest args)))]
      (println (str "\n" test " tests, " (+ pass fail error) " assertions, "
                   fail " failures, " error " errors."))
      (when (pos? (+ fail error))
        (System/exit 1)))
    (let [results (doall
                   (for [ns test-namespaces]
                     (let [{:keys [out exit]} (sh/sh "jolt" "-M:test" "--serial" (str ns))]
                       (print out)
                       [exit out])))
          failures (filter #(pos? (first %)) results)]
      (when (seq failures)
        (System/exit 1))
      (println "\nall namespaces green."))))

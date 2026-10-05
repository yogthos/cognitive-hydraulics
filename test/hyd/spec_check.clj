(ns hyd.spec-check
  "Runs the writ specs.

    jolt -M:check                every spec
    jolt -M:check hyd.actr-spec  just these"
  (:require [writ.spec :as spec]))

(def spec-namespaces
  '[hyd.impasse-spec
    hyd.pressure-spec
    hyd.actr-spec
    hyd.memory-spec
    hyd.agent-spec])

(defn -main [& args]
  (let [nss (if (seq args) (map symbol args) spec-namespaces)
        reports (doall (for [ns nss]
                         (let [r (spec/check ns)]
                           (println (:message r))
                           r)))]
    (when (some #(not (:ok %)) reports)
      (System/exit 1))))

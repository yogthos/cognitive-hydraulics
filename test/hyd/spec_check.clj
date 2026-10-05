(ns hyd.spec-check
  "Runs the writ specs: jolt -M:check"
  (:require [writ.spec :as spec]))

(def spec-namespaces
  '[hyd.pressure-spec
    hyd.actr-spec])

(defn -main [& _]
  (let [reports (map #(spec/check %) spec-namespaces)]
    (doseq [r reports]
      (println (:message r)))
    (when (some #(not (:ok %)) reports)
      (System/exit 1))))

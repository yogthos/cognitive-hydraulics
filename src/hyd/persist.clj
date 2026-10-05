(ns hyd.persist
  "Chunk-store durability as plain EDN. The only IO the library ships, kept
  out of the pure core so hyd.memory stays checkable."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [hyd.memory :as memory]))

(defn save!
  "Write the store to an EDN file."
  [store path]
  (spit path (pr-str store)))

(defn load-store
  "Read a store from an EDN file; empty when absent."
  [path]
  (if (.exists (io/file path))
    (edn/read-string (slurp path))
    (memory/store)))

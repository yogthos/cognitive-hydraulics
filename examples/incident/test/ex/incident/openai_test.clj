(ns ex.incident.openai-test
  "The OpenAI-compatible adapter, as an example-owned engine: payload
  building, reply parsing and response decoding are pure, so they stay
  tested without any network."
  (:require [clojure.test :refer [deftest is testing]]
            [ex.incident.openai :as openai]))

(def ops
  [{:op :move :args {:b :a :to :b}}
   {:op :move :args {:b :b :to :a}}])

(deftest estimate-prompt-building
  (testing "the wire payload carries the operators and demands JSON"
    (let [payload (openai/estimate-payload ops {:state {:on {:a :table}}})
          sys (some :content (filter #(= :system (:role %)) (:messages payload)))]
      (is (re-find #"JSON" sys))
      (is (= 2 (count (:messages payload))))))
  (testing "json mode uses the wire name: response_format, not response-format"
    (let [payload (openai/estimate-payload ops {})]
      (is (= {:type "json_object"} (:response_format payload)))
      (is (nil? (:response-format payload))))))

(deftest estimate-response-parsing
  (testing "a well-formed JSON reply parses to operator estimates"
    (let [reply "{\"move|a|b\": {\"p\": 0.9, \"c\": 1.0}}"
          parsed (openai/parse-estimates reply ops)]
      (is (= {:p 0.9 :c 1.0}
             (get parsed {:op :move :args {:b :a :to :b}})))))
  (testing "garbage parses to an empty map"
    (is (= {} (openai/parse-estimates "no json here" ops)))))

(def ok-body
  "{\"choices\": [{\"message\": {\"role\": \"assistant\", \"content\": \"world\"}}]}")

(deftest reply-content-extraction
  (testing "a 200 with a chat-completions body yields the assistant text"
    (is (= "world" (openai/reply-content {:status 200 :body ok-body}))))
  (testing "an error status yields nil"
    (is (nil? (openai/reply-content {:status 401 :body "{\"error\": {\"message\": \"bad key\"}}"})))
    (is (nil? (openai/reply-content {:status 429 :body "slow down"}))))
  (testing "a 200 with a garbage body yields nil"
    (is (nil? (openai/reply-content {:status 200 :body "<html>gateway</html>"})))))

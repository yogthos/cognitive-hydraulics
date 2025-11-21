"""Reasoning engines: Soar, ACT-R, and meta-cognitive monitoring."""

from cognitive_hydraulics.engine.rule_engine import Rule, RuleEngine
from cognitive_hydraulics.engine.meta_monitor import MetaCognitiveMonitor, CognitiveMetrics
from cognitive_hydraulics.engine.impasse import Impasse, ImpasseType, ImpasseDetector
from cognitive_hydraulics.engine.cognitive_agent import CognitiveAgent
from cognitive_hydraulics.engine.actr_resolver import ACTRResolver

__all__ = [
    "Rule",
    "RuleEngine",
    "MetaCognitiveMonitor",
    "CognitiveMetrics",
    "Impasse",
    "ImpasseType",
    "ImpasseDetector",
    "CognitiveAgent",
    "ACTRResolver",
]


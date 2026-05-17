"""Black-box behavioral evaluation via frontier LLM APIs.

This module sends the original prompt and a rewritten prompt to an LLM API,
then scores the output pair on each behavioral axis to verify whether
StateProbe's diagnosis is actionable.
"""

from stateprobe.eval.scorer import BEHAVIOR_RUBRICS
from stateprobe.eval.client import DEFAULT_EVAL_MODEL

__all__ = [
    "BEHAVIOR_RUBRICS",
    "DEFAULT_EVAL_MODEL",
]

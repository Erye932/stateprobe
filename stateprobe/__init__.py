"""StateProbe — Prompt State Debugger.

Diagnose which behavioral vectors your prompt activates in an LLM,
identify pollution sources, and get rewrite suggestions to reach a target state.

Theoretical foundation:
- Anthropic, "Persona Vectors: Monitoring and Controlling Character Traits in
  Language Models" (arXiv:2507.21509, 2025)
- DeepSeek-AI, "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via
  Reinforcement Learning" (arXiv:2501.12948, 2025)
"""

__version__ = "0.1.0"

from stateprobe.models import (
    Axis,
    AxisReading,
    PollutionSource,
    Report,
    TargetPreset,
)
from stateprobe.detector import diagnose
from stateprobe.rewriter import suggest_rewrite

__all__ = [
    "Axis",
    "AxisReading",
    "PollutionSource",
    "Report",
    "TargetPreset",
    "diagnose",
    "suggest_rewrite",
    "__version__",
]

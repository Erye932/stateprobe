"""StateProbe evidence contributors.

Per ADR_009, contributors observe a prompt and emit PollutionSource evidence
that the detector aggregates into per-axis readings. Multiple contributors
can run in parallel; their evidence merges into the same per-axis pool.

- StaticRuleContributor (v0.1+): regex rules, always-on, deterministic
- LLMJudgeContributor (v0.2+): LLM semantic judging, opt-in, needs API key
- LabContributor (v0.3+): hidden-state activation projection on
  DeepSeek-R1-Distill-Qwen via Persona Vectors (ADR_010), needs GPU
- EmbeddingContributor (planned): local embedding fallback for users
  who can't run a model but want a third evidence layer

Backward-compat aliases (Engine / StaticEngine / LLMJudgeEngine) are
deprecated and will be removed in v0.4.

`LabContributor` lives in `stateprobe.engines.lab` and is imported lazily;
importing this package does not require torch / transformers.
"""

from stateprobe.engines.base import (
    Engine,
    EngineError,
    EngineUnavailable,
    EvidenceContributor,
)
from stateprobe.engines.static import StaticEngine, StaticRuleContributor
from stateprobe.engines.llm_judge import LLMJudgeContributor, LLMJudgeEngine

__all__ = [
    "EvidenceContributor",
    "EngineError",
    "EngineUnavailable",
    "StaticRuleContributor",
    "LLMJudgeContributor",
    "LabContributor",  # lazy-loaded; see __getattr__
    # Deprecated aliases:
    "Engine",
    "StaticEngine",
    "LLMJudgeEngine",
]


def __getattr__(name):
    """Lazy import for LabContributor so we don't drag in torch on `import stateprobe`."""
    if name == "LabContributor":
        from stateprobe.engines.lab import LabContributor as _LabContributor
        return _LabContributor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

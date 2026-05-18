"""StateProbe evidence contributors.

Per ADR_009, contributors observe a prompt and emit PollutionSource evidence
that the detector aggregates into per-axis readings. Multiple contributors
can run in parallel; their evidence merges into the same per-axis pool.

- StaticRuleContributor (v0.1+): regex rules, always-on, deterministic
- LLMJudgeContributor (v0.2+): LLM semantic judging, opt-in, needs API key
- EmbeddingContributor (v0.3, planned): local embedding fallback
- LabContributor (v0.4, planned): hidden-state activation projection

Backward-compat aliases (Engine / StaticEngine / LLMJudgeEngine) are
deprecated and will be removed in v0.3.
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
    # Deprecated aliases:
    "Engine",
    "StaticEngine",
    "LLMJudgeEngine",
]

"""Evidence contributor abstraction.

Per ADR_009, a contributor is anything that observes a prompt and produces
zero-or-more pieces of axis evidence. Multiple contributors run in parallel
and their evidence merges into the same per-axis pool before aggregation.

Concrete contributors:
- StaticRuleContributor (v0.1+): regex rules, always-on, deterministic
- LLMJudgeContributor (v0.2+): LLM semantic judging, opt-in, requires API
- EmbeddingContributor (v0.3, planned): local embedding fallback
- LabContributor (v0.4, planned): hidden-state activation projection

Design invariants:
1. Sensors are dumb: they emit evidence (PollutionSource[]), never readings.
2. Aggregation is single: the detector module owns the only aggregation rule.
3. Evidence is uniform: every contributor emits PollutionSource with
   `weight` (signal strength) and `confidence` (observer certainty).
4. Optional contributors fail silently: the orchestrator catches
   EngineUnavailable and continues with whatever evidence the others produced.

Backward-compat: the legacy `Engine` protocol (returning Dict[Axis, AxisReading])
is kept as a deprecated alias. Calls into it from outside the package may
still work in v0.2 but will be removed in v0.3.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable

from stateprobe.models import Axis, AxisReading, ModelBaseline, PollutionSource


class EngineError(RuntimeError):
    """Fatal engine / contributor failure that should not be auto-recovered."""


class EngineUnavailable(EngineError):
    """Recoverable contributor failure (missing API key, model not loaded, etc.).

    The hybrid detector catches this, drops the contributor, and emits a
    RuntimeWarning (v0.3+). Other contributors still produce a result.
    """


@runtime_checkable
class EvidenceContributor(Protocol):
    """Protocol for prompt → axis evidence (the v0.2+ hybrid abstraction)."""

    name: str

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[PollutionSource]]:
        """Return zero or more PollutionSource per axis observed in the prompt.

        Contributors only emit *positive evidence* — sources that actually
        attribute pressure on an axis. They never emit synthetic "no signal"
        sources; the absence of evidence is itself the signal that the axis
        sits at baseline.

        Args:
            prompt: User's prompt text.
            baseline: Optional model baseline. Contributors may use this to
                decide what counts as "above baseline".

        Returns:
            Dict where every Axis is a key (may map to empty list). Values
            are lists because multiple sources can attribute to one axis.

        Raises:
            EngineUnavailable: Recoverable failure (missing key, network).
                The orchestrator will silently drop this contributor.
            EngineError: Fatal misuse (malformed responses, etc.). Surfaced.
        """
        ...


# ---------------------------------------------------------------------------
# Deprecated: legacy Engine protocol (returns full AxisReading per axis).
# Kept for one version so external callers don't break instantly. Will be
# removed in v0.3.
# ---------------------------------------------------------------------------

@runtime_checkable
class Engine(Protocol):
    """DEPRECATED: legacy v0.2.0.dev0 protocol. Use EvidenceContributor.

    Returns full readings instead of evidence. Will be removed in v0.3.
    """

    name: str

    def read_axes(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, AxisReading]:
        ...

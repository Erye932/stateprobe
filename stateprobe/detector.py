"""Detection orchestrator (hybrid evidence pipeline, ADR_009).

Pipeline:
  prompt
    → contributors (parallel, each emits PollutionSource[] per axis)
    → merged evidence pool
    → aggregator (pure function: confidence-filter → tanh sum)
    → per-axis AxisReading

The aggregator is the only place that combines evidence into a number. Every
contributor goes through the same formula, regardless of whether it's a
deterministic regex match or a fuzzy LLM observation. Confidence (carried
on each source) controls whether the source contributes at all.

Empty / trivial prompts: contributors return empty source lists; readings
sit at the model baseline; `diagnose()` marks `is_trivial=True` so the
report suppresses suggestions and overlap warnings.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from stateprobe.engines.base import EvidenceContributor

from stateprobe.models import (
    Axis,
    AxisDelta,
    AxisReading,
    BaselineOverlap,
    ModelBaseline,
    PollutionSource,
    Report,
    StructuralWarning,
    TargetPreset,
)
from stateprobe.structural import detect_structural_issues
from stateprobe.rules import (
    DEFAULT_MODEL_BASELINE,
    DEFAULT_TARGET,
    get_model_baseline,
    get_target,
)
from stateprobe.rewriter import suggest_rewrite


# ---------------------------------------------------------------------------
# Aggregation (pure)
# ---------------------------------------------------------------------------

# Sources below this confidence are filtered out before aggregation. They
# may still appear in debug logs but they do not move readings or count
# toward `is_trivial` detection. Aligned with MIN_LLM_CONFIDENCE so the
# LLM contributor's confidence threshold matches the aggregator's.
MIN_AGGREGATE_CONFIDENCE = 0.30

# Tanh saturation curve coefficient. Higher = sharper saturation.
# At net pressure 1.0, reading = 0.5 + 0.5*tanh(0.8) ≈ 0.83.
# At net pressure 2.0, reading = 0.5 + 0.5*tanh(1.6) ≈ 0.96.
_SATURATION_K = 0.8


def _baseline_for(axis: Axis, baseline: Optional[ModelBaseline]) -> float:
    if baseline is None:
        return 0.5
    return baseline.axis_baselines.get(axis, 0.5)


def _aggregate_one_axis(
    sources: List[PollutionSource],
    baseline: float,
) -> float:
    """Combine pollution sources on one axis into a single 0-1 reading.

    The reading starts at the model's meta-instruction baseline (not 0.5).
    Each source contributes direction * weight * confidence to net pressure;
    sources below MIN_AGGREGATE_CONFIDENCE are already filtered upstream.

    With no qualifying sources: returns baseline.
    With positive net pressure: shifts up toward 1.0 via tanh saturation.
    With negative net pressure: shifts down toward 0.0 via tanh saturation.
    """
    if not sources:
        return baseline
    net_pressure = sum(s.direction * s.weight * s.confidence for s in sources)
    saturated = math.tanh(_SATURATION_K * net_pressure)
    if saturated >= 0:
        return baseline + saturated * (1.0 - baseline)
    else:
        return baseline + saturated * baseline


def _aggregate_to_readings(
    sources_by_axis: Dict[Axis, List[PollutionSource]],
    baseline: Optional[ModelBaseline] = None,
) -> Dict[Axis, AxisReading]:
    """Pure function: merged-evidence pool → per-axis AxisReading.

    Filters out low-confidence sources, then runs the per-axis aggregator.
    This is the only place the project combines evidence into numbers,
    regardless of which contributor produced the evidence.
    """
    readings: Dict[Axis, AxisReading] = {}
    for axis in Axis:
        all_sources = sources_by_axis.get(axis, [])
        kept = [
            s for s in all_sources if s.confidence >= MIN_AGGREGATE_CONFIDENCE
        ]
        kept.sort(key=lambda s: s.weight * s.confidence, reverse=True)
        readings[axis] = AxisReading(
            axis=axis,
            value=_aggregate_one_axis(kept, baseline=_baseline_for(axis, baseline)),
            contributing_sources=kept,
        )
    return readings


# ---------------------------------------------------------------------------
# Main detection API
# ---------------------------------------------------------------------------

def detect_readings(
    prompt: str,
    baseline: Optional[ModelBaseline] = None,
    contributors: Optional[Sequence["EvidenceContributor"]] = None,
) -> Dict[Axis, AxisReading]:
    """Run all contributors against the prompt, merge their evidence, aggregate.

    Args:
        prompt: The user's prompt text.
        baseline: Optional model baseline. Anchors per-axis zero-pressure.
        contributors: Optional list of evidence contributors. Defaults to
            [StaticRuleContributor()] for backward compat with v0.1 calls.

    Returns:
        Dict mapping each Axis to its AxisReading. Empty prompts produce
        readings equal to the model baseline (no contributors will emit
        evidence for empty input).

    Failure handling: any contributor that raises EngineUnavailable is
    silently dropped — the remaining contributors still produce a result.
    EngineError (fatal) propagates.
    """
    # Lazy import to avoid circular dependency: engines.static imports
    # nothing from detector, but detector is imported by engines.static's
    # deprecated wrapper.
    if contributors is None:
        from stateprobe.engines import StaticRuleContributor

        contributors = [StaticRuleContributor()]

    # Lazy import to avoid hard dep cycle.
    from stateprobe.engines.base import EngineUnavailable

    merged: Dict[Axis, List[PollutionSource]] = {axis: [] for axis in Axis}
    for contributor in contributors:
        try:
            partial = contributor.contribute(prompt, baseline=baseline)
        except EngineUnavailable:
            # Optional contributor missing key / unreachable → silent drop.
            continue
        for axis, srcs in partial.items():
            merged[axis].extend(srcs)

    return _aggregate_to_readings(merged, baseline=baseline)


def compute_deltas(
    readings: Dict[Axis, AxisReading],
    target: TargetPreset,
) -> Dict[Axis, AxisDelta]:
    """Compute current-vs-target delta for each axis."""
    deltas: Dict[Axis, AxisDelta] = {}
    for axis in Axis:
        deltas[axis] = AxisDelta(
            axis=axis,
            current=readings[axis].value,
            target=target.coordinates.get(axis, 0.5),
        )
    return deltas


_OVERLAP_TEMPLATES_ZH: Dict[Axis, str] = {
    Axis.REASONING_BUDGET: (
        "DeepSeek 元指令已预设'尽最大努力，不允许捷径'（基线 {baseline:.0%}），"
        "你的提示词在此轴上再加压（{user:.0%}）→ 过载，建议删除推理指令"
    ),
    Axis.TASK_WIDTH: (
        "DeepSeek 元指令已预设'所有潜在路径、极端情况'（基线 {baseline:.0%}），"
        "你的提示词进一步扩宽（{user:.0%}）→ 范围爆炸，建议收窄"
    ),
    Axis.SELF_VERIFICATION: (
        "DeepSeek 元指令已预设'记录每一步、每个假设'（基线 {baseline:.0%}），"
        "你的提示词再加验证指令（{user:.0%}）→ 无限展开，建议改为给验收标准"
    ),
    Axis.IDENTITY_STRENGTH: (
        "专家人设触发情绪向量偏移（Anthropic 2026 证实），"
        "叠加 DeepSeek 高推理预算基线 → 三重过载，建议删除人设"
    ),
}

_GENERIC_OVERLAP_ZH = (
    "模型元指令已在此轴预设较高基线（{baseline:.0%}），"
    "你的提示词继续加压（{user:.0%}）→ 可能过载"
)


def _detect_overlaps(
    readings: Dict[Axis, AxisReading],
    baseline: ModelBaseline,
    target: Optional[TargetPreset] = None,
) -> List[BaselineOverlap]:
    """Find axes where prompt + baseline + target genuinely conflict.

    A warning is only emitted when:
    - The model baseline conflicts with the target by at least 0.30
      (i.e., baseline pushes one way, target wants the other), AND
    - The user prompt provides no counter-signal on that axis OR
      actively amplifies the saturated baseline.

    This avoids flooding the user with warnings on every prompt.
    """
    overlaps: List[BaselineOverlap] = []
    for axis in Axis:
        reading = readings[axis]
        user_val = reading.value
        base_val = baseline.axis_baselines.get(axis, 0.5)
        sources = reading.contributing_sources
        positive_pressure = sum(s.weight for s in sources if s.direction > 0)
        negative_pressure = sum(s.weight for s in sources if s.direction < 0)
        net_pressure = positive_pressure - negative_pressure

        # Skip axes where baseline is neutral
        if not baseline.is_saturated(axis):
            continue

        # Skip if there's no target or target also wants this axis high
        if target is not None:
            target_val = target.coordinates.get(axis, 0.5)
            conflict = base_val - target_val
            if conflict < 0.30:
                # Baseline is high but target also wants it high - no conflict
                continue

        if net_pressure > 0.15:
            # User amplifying a saturated axis - hard overload
            template = _OVERLAP_TEMPLATES_ZH.get(axis, _GENERIC_OVERLAP_ZH)
            overlaps.append(BaselineOverlap(
                axis=axis,
                user_pressure=user_val,
                model_baseline=base_val,
                warning_zh=template.format(baseline=base_val, user=user_val),
            ))
        elif negative_pressure < 0.15:
            # User provides essentially no counter-signal
            # Baseline will dominate, but target conflicts with baseline
            overlaps.append(BaselineOverlap(
                axis=axis,
                user_pressure=user_val,
                model_baseline=base_val,
                warning_zh=(
                    f"DeepSeek 元指令预设 {axis.label_zh} 基线 {base_val:.0%}，"
                    f"你的目标态需要 {target.coordinates.get(axis, 0.5):.0%}。"
                    f"提示词无反向约束 → 输出会偏向冗长/发散"
                ),
            ))
    return overlaps


# Length threshold separating "too short to diagnose" from "no anti-patterns
# found". Both cases suppress suggestions, but the user-facing message differs.
_TRIVIAL_PROMPT_THRESHOLD = 10


def diagnose(
    prompt: str,
    target_name: str = DEFAULT_TARGET,
    model_name: Optional[str] = DEFAULT_MODEL_BASELINE,
    *,
    llm_augment: Optional["EvidenceContributor"] = None,
    contributors: Optional[Sequence["EvidenceContributor"]] = None,
    engine: Optional["EvidenceContributor"] = None,
) -> Report:
    """High-level entry point: prompt + target name → full diagnostic Report.

    Default behavior (no contributors passed) is identical to v0.1: only the
    static rule contributor runs. This preserves backward compatibility for
    every existing caller.

    Args:
        prompt: The user's prompt text.
        target_name: Name of the target preset (default: calm_reasoning).
        model_name: Name of the model baseline for meta-instruction awareness.
            Use None to skip baseline overlap detection.
        llm_augment: Opt-in semantic layer. When provided, runs alongside the
            static contributor; their evidence merges in the aggregator.
            Pass None (default) for static-only diagnosis.
        contributors: Advanced — explicitly provide the full contributor list,
            overriding the default static + optional llm_augment composition.
            Useful for tests and custom layering.
        engine: DEPRECATED v0.2.0.dev0 alias. If given, it's wrapped as a
            single contributor. Will be removed in v0.3 — migrate to
            `llm_augment` or `contributors`.
    """
    target = get_target(target_name)
    baseline = get_model_baseline(model_name) if model_name else None

    # Resolve contributor list. Priority: explicit `contributors` >
    # legacy `engine` shim > [static] + optional llm_augment.
    if contributors is None:
        if engine is not None:
            # Legacy v0.2.0.dev0 path: treat engine as the sole contributor.
            # If it's the old Engine protocol (has read_axes but not
            # contribute), wrap it through the deprecated aliases path —
            # but in practice the deprecated wrappers already delegate to
            # the new contributors, so passing them here is safe.
            contributors_list = [_as_contributor(engine)]
        else:
            from stateprobe.engines import StaticRuleContributor

            contributors_list = [StaticRuleContributor()]
            if llm_augment is not None:
                contributors_list.append(_as_contributor(llm_augment))
    else:
        contributors_list = list(contributors)

    readings = detect_readings(prompt, baseline=baseline, contributors=contributors_list)
    deltas = compute_deltas(readings, target)
    structural_warnings = detect_structural_issues(prompt)

    # Trivial detection: if no qualifying evidence emerged from any
    # contributor for any axis, suppress reasoner output. Otherwise the
    # rewriter would hallucinate "remove X" advice for X never present in
    # the prompt. This also covers the case where LLM judge produced only
    # low-confidence observations that the aggregator filtered out.
    total_sources = sum(len(r.contributing_sources) for r in readings.values())
    is_trivial = (total_sources == 0)

    if is_trivial:
        suggestions = []
        overlaps = []
    else:
        suggestions = suggest_rewrite(readings, deltas, target)
        overlaps = _detect_overlaps(readings, baseline, target) if baseline else []

    return Report(
        prompt=prompt,
        readings=readings,
        target=target,
        deltas=deltas,
        suggestions=suggestions,
        model_baseline=baseline,
        baseline_overlaps=overlaps,
        structural_warnings=structural_warnings,
        is_trivial=is_trivial,
    )


def _as_contributor(obj) -> "EvidenceContributor":
    """Coerce a v0.2.0.dev0 `Engine` (read_axes) into a `EvidenceContributor`.

    If `obj` already implements `contribute`, returns it as-is. Otherwise
    wraps the legacy `read_axes` call so its returned readings become a
    flat list of PollutionSource per axis.
    """
    if hasattr(obj, "contribute"):
        return obj

    class _LegacyEngineAdapter:
        name = getattr(obj, "name", "legacy_engine")

        def __init__(self, inner):
            self._inner = inner

        def contribute(self, prompt, baseline=None):
            readings = self._inner.read_axes(prompt, baseline=baseline)
            out: Dict[Axis, List[PollutionSource]] = {axis: [] for axis in Axis}
            for axis, reading in readings.items():
                out[axis].extend(reading.contributing_sources)
            return out

    return _LegacyEngineAdapter(obj)

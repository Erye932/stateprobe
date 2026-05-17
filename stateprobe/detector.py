"""Detection engine.

Given a prompt, match it against the rule library and compute readings on
each of the 8 axes. Uses a tanh-saturated weighted-sum aggregation so that:

- A single strong rule shifts the reading meaningfully.
- Multiple aligned rules accumulate with diminishing returns (no runaway).
- Opposing rules cancel symmetrically.

Each matched rule is recorded as a PollutionSource so the report can explain
*why* each axis ended up where it did.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from stateprobe.models import (
    Axis,
    AxisDelta,
    AxisReading,
    BaselineOverlap,
    ModelBaseline,
    PollutionSource,
    Report,
    Rule,
    TargetPreset,
)
from stateprobe.rules import (
    ALL_RULES,
    DEFAULT_MODEL_BASELINE,
    DEFAULT_TARGET,
    get_model_baseline,
    get_target,
)
from stateprobe.rewriter import suggest_rewrite


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _find_matches(prompt: str, rule: Rule) -> List[str]:
    """Return all unique text spans in `prompt` that match any of the rule's
    patterns. Returns empty list if no match."""
    matches: List[str] = []
    seen = set()
    for pattern in rule.patterns:
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Skip malformed patterns silently — rule authors should test.
            continue
        for m in compiled.finditer(prompt):
            text = m.group(0)
            if text not in seen:
                seen.add(text)
                matches.append(text)
    return matches


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Tanh saturation curve coefficient. Higher = sharper saturation.
# At net pressure 1.0, reading = 0.5 + 0.5*tanh(0.8) ≈ 0.83.
# At net pressure 2.0, reading = 0.5 + 0.5*tanh(1.6) ≈ 0.96.
_SATURATION_K = 0.8


def _aggregate(sources: List[PollutionSource], baseline: float = 0.5) -> float:
    """Combine pollution sources on one axis into a single 0-1 reading.

    The reading starts at the model's meta-instruction baseline (not at 0.5).
    Detected rule pressure shifts it up/down from that baseline.

    This reflects the Anthropic activation-vector picture: even an empty
    prompt has non-neutral activations driven by the model's meta-instruction.

    With no rules matched: returns baseline (model's preset activation).
    With positive pressure: shifts upward, bounded by tanh saturation toward 1.
    With negative pressure: shifts downward, bounded by tanh saturation toward 0.
    """
    if not sources:
        return baseline
    net_pressure = sum(s.direction * s.weight for s in sources)
    # Map pressure to [-baseline, 1-baseline] range using tanh saturation,
    # so that the result stays in [0, 1] while preserving baseline as the
    # zero-pressure resting point.
    saturated = math.tanh(_SATURATION_K * net_pressure)
    if saturated >= 0:
        # Push from baseline toward 1.0
        return baseline + saturated * (1.0 - baseline)
    else:
        # Push from baseline toward 0.0
        return baseline + saturated * baseline


# ---------------------------------------------------------------------------
# Main detection API
# ---------------------------------------------------------------------------

def detect_readings(
    prompt: str,
    baseline: Optional[ModelBaseline] = None,
) -> Dict[Axis, AxisReading]:
    """Run all rules against the prompt and return per-axis readings.

    Each AxisReading.value is in [0, 1] where the starting point is the
    model's meta-instruction baseline (not 0.5 neutral).

    Args:
        prompt: The user's prompt text.
        baseline: Optional model baseline. If None, uses neutral 0.5 baseline.

    Each AxisReading.contributing_sources lists every rule that matched.
    Empty prompt returns the model's baseline readings (reflecting the fact
    that even with no user input, meta-instructions still activate vectors).
    """
    def _baseline_for(axis: Axis) -> float:
        if baseline is None:
            return 0.5
        return baseline.axis_baselines.get(axis, 0.5)

    if not prompt or not prompt.strip():
        # Empty prompt → readings equal the model's meta-instruction baseline.
        return {
            axis: AxisReading(axis=axis, value=_baseline_for(axis))
            for axis in Axis
        }

    # Bucket pollution sources by axis.
    sources_by_axis: Dict[Axis, List[PollutionSource]] = {axis: [] for axis in Axis}

    for rule in ALL_RULES:
        matches = _find_matches(prompt, rule)
        if not matches:
            continue
        representative = matches[0]
        source = PollutionSource(
            rule_id=rule.id,
            axis=rule.axis,
            direction=rule.direction,
            weight=rule.weight,
            matched_text=representative,
            explanation_zh=rule.explanation_zh,
            citation=rule.citation,
        )
        sources_by_axis[rule.axis].append(source)

    # Build readings, anchored to the model baseline.
    readings: Dict[Axis, AxisReading] = {}
    for axis in Axis:
        sources = sources_by_axis[axis]
        sources.sort(key=lambda s: s.weight, reverse=True)
        readings[axis] = AxisReading(
            axis=axis,
            value=_aggregate(sources, baseline=_baseline_for(axis)),
            contributing_sources=sources,
        )
    return readings


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


def diagnose(
    prompt: str,
    target_name: str = DEFAULT_TARGET,
    model_name: Optional[str] = DEFAULT_MODEL_BASELINE,
) -> Report:
    """High-level entry point: prompt + target name → full diagnostic Report.

    Args:
        prompt: The user's prompt text.
        target_name: Name of the target preset (default: calm_reasoning).
        model_name: Name of the model baseline for meta-instruction awareness.
            Use None to skip baseline overlap detection.
    """
    target = get_target(target_name)
    baseline = get_model_baseline(model_name) if model_name else None
    readings = detect_readings(prompt, baseline=baseline)
    deltas = compute_deltas(readings, target)
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
    )

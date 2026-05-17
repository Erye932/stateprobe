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
    PollutionSource,
    Report,
    Rule,
    TargetPreset,
)
from stateprobe.rules import ALL_RULES, DEFAULT_TARGET, get_target
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


def _aggregate(sources: List[PollutionSource]) -> float:
    """Combine pollution sources on one axis into a single 0-1 reading.

    Uses tanh-saturated weighted sum centered at 0.5 (neutral)."""
    if not sources:
        return 0.5
    net_pressure = sum(s.direction * s.weight for s in sources)
    return 0.5 + 0.5 * math.tanh(_SATURATION_K * net_pressure)


# ---------------------------------------------------------------------------
# Main detection API
# ---------------------------------------------------------------------------

def detect_readings(prompt: str) -> Dict[Axis, AxisReading]:
    """Run all rules against the prompt and return per-axis readings.

    Each AxisReading.value is in [0, 1] where 0.5 is neutral.
    Each AxisReading.contributing_sources lists every rule that matched.
    """
    if not prompt or not prompt.strip():
        # Empty prompt → all axes neutral with no sources.
        return {axis: AxisReading(axis=axis, value=0.5) for axis in Axis}

    # Bucket pollution sources by axis.
    sources_by_axis: Dict[Axis, List[PollutionSource]] = {axis: [] for axis in Axis}

    for rule in ALL_RULES:
        matches = _find_matches(prompt, rule)
        if not matches:
            continue
        # If a rule matches multiple times in one prompt, we still only count
        # it once (per-rule effect). But we record the first matched span as
        # representative for the explanation.
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

    # Build readings.
    readings: Dict[Axis, AxisReading] = {}
    for axis in Axis:
        sources = sources_by_axis[axis]
        # Sort sources by absolute contribution descending for explanation order.
        sources.sort(key=lambda s: s.weight, reverse=True)
        readings[axis] = AxisReading(
            axis=axis,
            value=_aggregate(sources),
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


def diagnose(
    prompt: str,
    target_name: str = DEFAULT_TARGET,
) -> Report:
    """High-level entry point: prompt + target name → full diagnostic Report.

    This is what the CLI and downstream tools should call.
    """
    target = get_target(target_name)
    readings = detect_readings(prompt)
    deltas = compute_deltas(readings, target)
    suggestions = suggest_rewrite(readings, deltas, target)
    return Report(
        prompt=prompt,
        readings=readings,
        target=target,
        deltas=deltas,
        suggestions=suggestions,
    )

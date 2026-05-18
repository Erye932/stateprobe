"""Static rule contributor (v0.1+).

Per ADR_009, this contributor emits PollutionSource evidence by running the
regex rule library against the prompt. It does NOT compute readings — that
is the aggregator's job, and is shared across all contributors.

Strengths:
- Fast (milliseconds), free, fully offline.
- Fully explainable: every source traces to a specific matched span.
- Confidence is always 1.0 because regex matches are deterministic.

Limits:
- Coverage is bounded by the rule library. Patterns not anticipated by
  rule authors emit no source (axis stays at baseline).
- Cannot read semantic intent (e.g., a politely worded sycophancy bait).
  That gap is filled by LLMJudgeContributor when --llm-augment is enabled.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from stateprobe.engines.base import Engine, EvidenceContributor
from stateprobe.models import (
    Axis,
    AxisReading,
    ModelBaseline,
    PollutionSource,
    Rule,
)


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


class StaticRuleContributor:
    """Match the regex rule library against the prompt and emit evidence.

    Every emitted PollutionSource has confidence=1.0 because regex matches
    are deterministic (the pattern either matched or it didn't).
    """

    name = "static_rules"

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[PollutionSource]]:
        # Lazy import to avoid circular dependency at module load.
        from stateprobe.rules import ALL_RULES

        sources_by_axis: Dict[Axis, List[PollutionSource]] = {
            axis: [] for axis in Axis
        }
        if not prompt or not prompt.strip():
            return sources_by_axis

        for rule in ALL_RULES:
            matches = _find_matches(prompt, rule)
            if not matches:
                continue
            representative = matches[0]
            sources_by_axis[rule.axis].append(
                PollutionSource(
                    rule_id=rule.id,
                    axis=rule.axis,
                    direction=rule.direction,
                    weight=rule.weight,
                    matched_text=representative,
                    explanation_zh=rule.explanation_zh,
                    citation=rule.citation,
                    confidence=1.0,
                )
            )
        return sources_by_axis


# ---------------------------------------------------------------------------
# Deprecated: v0.2.0.dev0 alias. Will be removed in v0.3.
# Kept so external callers don't crash; emits a one-line notice via the
# Engine protocol path that wraps the contributor + aggregator.
# ---------------------------------------------------------------------------

class StaticEngine(Engine):
    """DEPRECATED: legacy v0.2.0.dev0 wrapper. Use StaticRuleContributor.

    Returns full readings (delegates to detect_readings() with the
    contributor as the only sensor). Will be removed in v0.3.
    """

    name = "static"

    def read_axes(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, AxisReading]:
        from stateprobe.detector import detect_readings

        return detect_readings(prompt, baseline=baseline)

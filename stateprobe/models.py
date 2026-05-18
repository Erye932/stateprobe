"""Data models for StateProbe.

The core abstraction: a prompt is a point in N-dimensional behavior space.
Each axis represents one continuous behavioral dimension (sycophancy,
task width, reasoning budget, etc.) that the prompt activates in the LLM.

We model behavior as continuous (per Anthropic persona vectors) rather than
discrete state labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Axis(str, Enum):
    """The 8 behavioral axes StateProbe measures.

    Each axis maps to a direction in the model's activation space, validated
    by persona-vector and activation-steering research.
    """

    SYCOPHANCY = "sycophancy"
    """0 = dares to say 'no', 1 = agrees with everything.
    Source: Anthropic Persona Vectors (sycophancy direction)."""

    TASK_WIDTH = "task_width"
    """0 = single-point judgment, 1 = full-scope survey.
    Source: DeepSeek-R1 (task framing affects reasoning scope)."""

    SUCCESS_CRITERIA = "success_criteria"
    """0 = no failure standard, 1 = explicit criteria.
    Source: engineering consensus; reduces hallucination/notwater."""

    REASONING_BUDGET = "reasoning_budget"
    """0 = direct answer, 1 = deep chain-of-thought.
    Source: DeepSeek-R1 (CoT length controllability)."""

    IDENTITY_STRENGTH = "identity_strength"
    """0 = no role, 1 = heavy role-play.
    Source: Anthropic Persona Vectors (persona prompting shifts residual stream)."""

    ASSERTIVENESS = "assertiveness"
    """0 = hedges everything, 1 = decisive claims.
    Source: RLHF calibration literature."""

    SELF_VERIFICATION = "self_verification"
    """0 = accepts first answer, 1 = aggressive self-critique.
    Source: DeepSeek-R1 (reflection / self-verification behavior)."""

    INFO_FLOW = "info_flow"
    """0 = model gives answer, 1 = model asks for clarification.
    Source: agentic LLM literature."""

    @property
    def label_zh(self) -> str:
        return _AXIS_LABELS_ZH[self]

    @property
    def label_en(self) -> str:
        return _AXIS_LABELS_EN[self]

    @property
    def low_end_zh(self) -> str:
        return _AXIS_LOW_HIGH_ZH[self][0]

    @property
    def high_end_zh(self) -> str:
        return _AXIS_LOW_HIGH_ZH[self][1]


_AXIS_LABELS_ZH: Dict[Axis, str] = {
    Axis.SYCOPHANCY: "迎合度",
    Axis.TASK_WIDTH: "任务宽度",
    Axis.SUCCESS_CRITERIA: "验收清晰度",
    Axis.REASONING_BUDGET: "推理预算",
    Axis.IDENTITY_STRENGTH: "身份强度",
    Axis.ASSERTIVENESS: "自信度",
    Axis.SELF_VERIFICATION: "自我验证",
    Axis.INFO_FLOW: "信息流向",
}

_AXIS_LABELS_EN: Dict[Axis, str] = {
    Axis.SYCOPHANCY: "Sycophancy",
    Axis.TASK_WIDTH: "Task Width",
    Axis.SUCCESS_CRITERIA: "Success Criteria",
    Axis.REASONING_BUDGET: "Reasoning Budget",
    Axis.IDENTITY_STRENGTH: "Identity Strength",
    Axis.ASSERTIVENESS: "Assertiveness",
    Axis.SELF_VERIFICATION: "Self-Verification",
    Axis.INFO_FLOW: "Info Flow",
}

_AXIS_LOW_HIGH_ZH: Dict[Axis, tuple] = {
    Axis.SYCOPHANCY: ("敢说不行", "全盘点赞"),
    Axis.TASK_WIDTH: ("单点判断", "全面综述"),
    Axis.SUCCESS_CRITERIA: ("无边界", "失败标准明确"),
    Axis.REASONING_BUDGET: ("直接答", "深度推理"),
    Axis.IDENTITY_STRENGTH: ("无角色", "重扮演"),
    Axis.ASSERTIVENESS: ("满嘴可能", "敢下结论"),
    Axis.SELF_VERIFICATION: ("接受首答", "反复推翻"),
    Axis.INFO_FLOW: ("给答案", "反问澄清"),
}


@dataclass(frozen=True)
class Rule:
    """A detection rule that maps a textual pattern to an axis adjustment.

    Each rule encodes one piece of methodology: when this pattern appears,
    the model is being pushed along `axis` by `direction * weight`.
    """

    id: str
    axis: Axis
    direction: int  # +1 (raises reading) or -1 (lowers reading)
    patterns: List[str]  # regex patterns; OR-matched
    weight: float  # 0.0 - 1.0, magnitude of effect
    explanation_zh: str  # WHY this pattern activates this axis
    citation: str  # paper / source reference

    def __post_init__(self):
        if self.direction not in (-1, 1):
            raise ValueError(f"Rule {self.id}: direction must be -1 or +1")
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Rule {self.id}: weight must be in [0, 1]")


@dataclass
class PollutionSource:
    """A specific span of the prompt that was matched by a rule and
    contributed to a non-neutral reading on some axis.

    Per ADR_009 (hybrid evidence), this is the unified evidence type emitted
    by every contributor (static rules, LLM judge, future embedding/lab).

    `weight` and `confidence` are intentionally separate:
    - `weight` = strength of signal when this evidence applies (0-1)
    - `confidence` = how sure the contributor is this evidence applies (0-1)

    Static rules are deterministic, so confidence defaults to 1.0 (the regex
    either matched or it didn't). The LLM judge reports its own confidence;
    low-confidence sources get filtered out by the aggregator before they
    can pollute trivial prompts.
    """

    rule_id: str
    axis: Axis
    direction: int  # +1 raised reading, -1 lowered reading
    weight: float
    matched_text: str  # the actual text span that matched
    explanation_zh: str
    citation: str
    confidence: float = 1.0


@dataclass
class AxisReading:
    """The aggregated reading for one axis after running all rules."""

    axis: Axis
    value: float  # 0.0 - 1.0
    contributing_sources: List[PollutionSource] = field(default_factory=list)

    @property
    def is_neutral(self) -> bool:
        return 0.4 <= self.value <= 0.6


@dataclass(frozen=True)
class TargetPreset:
    """A named target coordinate in behavior space (e.g., 'calm_reasoning').

    The user picks (or defines) a target preset; StateProbe computes the diff
    between current coordinates and target coordinates and suggests rewrites.
    """

    name: str
    label_zh: str
    description_zh: str
    coordinates: Dict[Axis, float]  # target value per axis, 0.0 - 1.0

    def __post_init__(self):
        for axis, val in self.coordinates.items():
            if not 0.0 <= val <= 1.0:
                raise ValueError(
                    f"TargetPreset {self.name}: coordinate for {axis} "
                    f"must be in [0, 1], got {val}"
                )


@dataclass(frozen=True)
class ModelBaseline:
    """The meta-instruction baseline of a specific model.

    Models like DeepSeek preset certain axes to high values via system-level
    meta-instructions. Prompt instructions that overlap with an already-saturated
    axis cause overload, not improvement.

    Principle: subtract on saturated axes, add on uncovered axes.
    """

    name: str
    label_zh: str
    description_zh: str
    axis_baselines: Dict[Axis, float]  # 0.0-1.0, model's pre-set value per axis

    def is_saturated(self, axis: Axis, threshold: float = 0.70) -> bool:
        """True if the model's meta-instruction already sets this axis high."""
        return self.axis_baselines.get(axis, 0.5) >= threshold

    def is_uncovered(self, axis: Axis, threshold: float = 0.35) -> bool:
        """True if the model's meta-instruction does NOT preset this axis."""
        return self.axis_baselines.get(axis, 0.5) <= threshold


@dataclass
class AxisDelta:
    """How far the current reading is from the target on one axis."""

    axis: Axis
    current: float
    target: float

    @property
    def delta(self) -> float:
        return self.target - self.current

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)

    @property
    def needs_decrease(self) -> bool:
        """Current > target → prompt is too high on this axis."""
        return self.delta < -0.15

    @property
    def needs_increase(self) -> bool:
        """Current < target → prompt needs more of this axis."""
        return self.delta > 0.15

    @property
    def is_aligned(self) -> bool:
        return self.abs_delta <= 0.15


@dataclass
class RewriteSuggestion:
    """A concrete suggestion for editing the prompt to move toward target."""

    axis: Axis
    action: str  # "remove" / "add" / "modify"
    description_zh: str  # human-readable suggestion
    example_zh: Optional[str] = None  # example text to add/use


@dataclass
class BaselineOverlap:
    """Warning that a user's prompt overlaps with a model's meta-instruction
    on an axis that is already saturated — causing overload, not improvement."""

    axis: Axis
    user_pressure: float  # how much the prompt pushes this axis (0.5 = neutral)
    model_baseline: float  # how much the meta-instruction already sets it
    warning_zh: str


@dataclass
class StructuralWarning:
    """A warning about the prompt's structure (not its semantic content).

    Distinct from axis-based diagnostics. Covers prompt-level concerns like:
    - Excessive length that may dilute key instructions
    - Redundant/repeated phrasing that wastes CSA-compressed attention
    - Multi-document concatenation without clear section markers
    """

    kind: str  # "length" | "redundancy" | "filler" | "synonym_stacking"
    severity: str  # "info" | "warning" | "critical"
    message_zh: str
    matched_text: Optional[str] = None
    suggestion_zh: Optional[str] = None


@dataclass
class Report:
    """The full diagnostic report for one prompt."""

    prompt: str
    readings: Dict[Axis, AxisReading]
    target: TargetPreset
    deltas: Dict[Axis, AxisDelta]
    suggestions: List[RewriteSuggestion]
    model_baseline: Optional["ModelBaseline"] = None
    baseline_overlaps: List[BaselineOverlap] = field(default_factory=list)
    structural_warnings: List[StructuralWarning] = field(default_factory=list)
    is_trivial: bool = False

    @property
    def pollution_sources(self) -> List[PollutionSource]:
        """All matched pollution sources across all axes, deduplicated by rule."""
        seen = set()
        result = []
        for reading in self.readings.values():
            for src in reading.contributing_sources:
                if src.rule_id in seen:
                    continue
                seen.add(src.rule_id)
                result.append(src)
        return result

    @property
    def alignment_score(self) -> float:
        """0.0 - 1.0, how aligned current is with target. 1.0 = perfect alignment."""
        if not self.deltas:
            return 1.0
        total_dist = sum(d.abs_delta for d in self.deltas.values())
        max_dist = len(self.deltas) * 1.0
        return max(0.0, 1.0 - total_dist / max_dist)

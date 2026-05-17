"""Rewrite suggestion generator.

Given (current readings, target coordinates, deltas), produce concrete,
actionable rewrite suggestions to move the prompt toward the target.

The strategy per axis with significant delta:
- If reading is TOO HIGH (delta negative): suggest removing the matched
  "+1" patterns AND/OR adding "-1" counter-language.
- If reading is TOO LOW (delta positive): suggest adding "+1" language.

Suggestions are templated per axis so the output is concrete (with example
text the user can copy-paste), not just abstract advice.
"""

from __future__ import annotations

from typing import Dict, List

from stateprobe.models import (
    Axis,
    AxisDelta,
    AxisReading,
    RewriteSuggestion,
    TargetPreset,
)


# ---------------------------------------------------------------------------
# Per-axis suggestion templates
# ---------------------------------------------------------------------------

# For each axis we provide:
#   "decrease": what to do when current > target (need to lower the reading)
#   "increase": what to do when current < target (need to raise the reading)
#
# Each entry has a (description, example) tuple.

_SUGGESTIONS: Dict[Axis, Dict[str, List[tuple]]] = {
    Axis.SYCOPHANCY: {
        "decrease": [
            (
                "删除迎合诱导词（'全面分析'、'优缺点'、'建议'等空泛框架）",
                None,
            ),
            (
                "加一句反迎合 permission，授予模型说'不'的权利",
                '不要鼓励，不要客套。如果这个方向不值得做，直接说不值得做。',
            ),
            (
                "把'失败'重新定义为有效输出",
                '失败也是有效结论。如果证据指向负面，直接给负面结论。',
            ),
        ],
        "increase": [
            (
                "如果你确实需要鼓励型输出，加入明确的赞赏请求",
                '请鼓励一下我，给出建设性的正面反馈。',
            ),
        ],
    },
    Axis.TASK_WIDTH: {
        "decrease": [
            (
                "删除'全面'、'各方面'、'综述'等扩宽词",
                None,
            ),
            (
                "把任务收窄成一个二元判断 / 单点结论",
                '判断 [X] 是否值得 [Y]：只要结论 + 最大风险 + 3 个证据。',
            ),
            (
                "加时间或数量边界",
                '本周内可执行的范围；最多 3 个点。',
            ),
        ],
        "increase": [
            (
                "如果确实需要宽任务，明确要求多视角覆盖",
                '从市场、技术、团队、用户 4 个维度各给一段分析。',
            ),
        ],
    },
    Axis.SUCCESS_CRITERIA: {
        "decrease": [
            (
                "删除'失败标准'、'可证伪'等强约束（一般不该降低这个轴）",
                None,
            ),
        ],
        "increase": [
            (
                "加显式失败标准 — 模型最强的注水抑制器",
                '失败标准：如果结论不能指导今天的取舍，就算失败。',
            ),
            (
                "加输出结构约束",
                '输出格式：结论一行 + 最大风险一行 + 3 个验证证据。',
            ),
            (
                "加拒绝条件",
                '如果信息不足以下判断，直接说"信息不足"，不要硬答。',
            ),
        ],
    },
    Axis.REASONING_BUDGET: {
        "decrease": [
            (
                "删除 'step by step' / '深度思考' / '多角度' 等扩展推理词",
                None,
            ),
            (
                "加速度约束",
                '直接给结论，不要解释过程。',
            ),
        ],
        "increase": [
            (
                "加 step-by-step 触发器",
                '请先一步一步推理，再给结论。',
            ),
            (
                "要求多角度",
                '从至少 3 个角度审视，再综合得出结论。',
            ),
        ],
    },
    Axis.IDENTITY_STRENGTH: {
        "decrease": [
            (
                "删除身份赋予句（'你是...专家'、'资深'、'扮演' 等）",
                None,
            ),
            (
                "改成纯任务描述，不绑定身份",
                '任务：[直接描述要做什么]。',
            ),
        ],
        "increase": [
            (
                "如确实需要特定视角，赋予明确角色（注意会引入迎合副作用）",
                '从产品经理视角审视：[任务]',
            ),
        ],
    },
    Axis.ASSERTIVENESS: {
        "decrease": [
            (
                "加 hedge 允许",
                '可以使用"可能"、"取决于"等表达不确定性。',
            ),
        ],
        "increase": [
            (
                "明确要求下结论",
                '必须给出明确结论（值得 / 不值得 / 信息不足三选一），不要含糊。',
            ),
            (
                "禁止 hedging",
                '不要使用"可能"、"也许"、"看情况"。',
            ),
        ],
    },
    Axis.SELF_VERIFICATION: {
        "decrease": [
            (
                "删除自我推翻 / 反例触发词",
                None,
            ),
        ],
        "increase": [
            (
                "要求模型至少考虑一个反例",
                '在给出结论前，先列举至少一个反例并解释为什么不成立。',
            ),
            (
                "要求自我推翻",
                '给出初步结论后，假设你是错的，论证反方观点，再决定是否修正。',
            ),
        ],
    },
    Axis.INFO_FLOW: {
        "decrease": [
            (
                "明确禁止反问",
                '基于我给你的信息直接回答，不要反问。',
            ),
        ],
        "increase": [
            (
                "授权模型在信息不足时反问",
                '如果信息不足以下判断，先列出你需要的额外信息，再决定是否回答。',
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Threshold for "significant" delta
# ---------------------------------------------------------------------------

# An axis is flagged for rewrite if |target - current| exceeds this.
SIGNIFICANT_DELTA_THRESHOLD = 0.20


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_rewrite(
    readings: Dict[Axis, AxisReading],
    deltas: Dict[Axis, AxisDelta],
    target: TargetPreset,
) -> List[RewriteSuggestion]:
    """Produce a list of concrete rewrite suggestions for axes that are
    significantly off-target.

    Suggestions are ordered by descending absolute delta, so the largest
    misalignment is addressed first.
    """
    # Sort axes by absolute delta descending — biggest gap first.
    flagged = [
        (axis, delta)
        for axis, delta in deltas.items()
        if delta.abs_delta >= SIGNIFICANT_DELTA_THRESHOLD
    ]
    flagged.sort(key=lambda pair: pair[1].abs_delta, reverse=True)

    suggestions: List[RewriteSuggestion] = []
    for axis, delta in flagged:
        templates = _SUGGESTIONS.get(axis, {})
        direction = "decrease" if delta.delta < 0 else "increase"
        action = "remove" if direction == "decrease" else "add"
        for desc, example in templates.get(direction, []):
            suggestions.append(
                RewriteSuggestion(
                    axis=axis,
                    action=action,
                    description_zh=desc,
                    example_zh=example,
                )
            )
    return suggestions

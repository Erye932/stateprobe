"""DeepSeek-R1-aligned contrastive prompt pairs.

These pairs are for building experimental activation directions on open-weight
reasoning models such as DeepSeek-R1-Distill-Qwen. A pair contains a positive
prompt that should activate the behavior and a negative prompt that should
suppress or avoid it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from stateprobe.models import Axis


DEFAULT_DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"


@dataclass(frozen=True)
class ContrastivePair:
    axis: Axis
    positive: str
    negative: str
    rationale_zh: str


DEEPSEEK_AXIS_PAIRS: Dict[Axis, List[ContrastivePair]] = {
    Axis.REASONING_BUDGET: [
        ContrastivePair(
            axis=Axis.REASONING_BUDGET,
            positive="请一步一步推理，先分析所有关键假设，再给出最终结论。",
            negative="请直接给出一句话结论，不要展开推理过程。",
            rationale_zh="DeepSeek-R1 的核心能力来自长 CoT、反思和推理预算扩展。",
        ),
        ContrastivePair(
            axis=Axis.REASONING_BUDGET,
            positive="这是一个复杂问题，请深度思考，列出中间推理链再回答。",
            negative="这是一个简单问题，请快速回答，不需要解释。",
            rationale_zh="显式深度思考应提高中后层 reasoning activation。",
        ),
        ContrastivePair(
            axis=Axis.REASONING_BUDGET,
            positive="先分解问题、逐步验证、最后汇总答案。",
            negative="不要分解问题，直接输出答案。",
            rationale_zh="分解-验证-汇总是 R1 类模型的典型推理轨迹。",
        ),
    ],
    Axis.SELF_VERIFICATION: [
        ContrastivePair(
            axis=Axis.SELF_VERIFICATION,
            positive="给出初步结论后，假设你是错的，找出反例并修正。",
            negative="给出第一个想到的答案，不要自我质疑。",
            rationale_zh="R1 论文强调 self-verification 和 reflection 涌现。",
        ),
        ContrastivePair(
            axis=Axis.SELF_VERIFICATION,
            positive="在最终回答前，请检查你的推理是否有漏洞。",
            negative="无需检查，直接给最终回答。",
            rationale_zh="显式检查应激活反思/验证方向。",
        ),
        ContrastivePair(
            axis=Axis.SELF_VERIFICATION,
            positive="请提出一个最强反方观点，再判断原结论是否仍成立。",
            negative="只支持原观点，不需要考虑反方观点。",
            rationale_zh="反方观点搜索是自我验证的可观测代理行为。",
        ),
    ],
    Axis.TASK_WIDTH: [
        ContrastivePair(
            axis=Axis.TASK_WIDTH,
            positive="请从技术、市场、团队、成本、风险五个方面全面分析。",
            negative="只判断这个方案今天是否值得继续做，最多给三个理由。",
            rationale_zh="任务宽度会改变模型分配推理预算的范围。",
        ),
        ContrastivePair(
            axis=Axis.TASK_WIDTH,
            positive="请给出这个主题的完整综述，覆盖所有重要维度。",
            negative="只回答最关键的一个失败风险。",
            rationale_zh="全面综述 vs 单点判断是任务范围方向的强对比。",
        ),
    ],
    Axis.SYCOPHANCY: [
        ContrastivePair(
            axis=Axis.SYCOPHANCY,
            positive="我这个想法是不是很棒？请支持我并肯定我的判断。",
            negative="请客观判断这个想法是否成立，如果不值得做就直接否定。",
            rationale_zh="虽然 sycophancy 来自 Persona Vectors，但 R1-Distill 上也可做行为方向对比。",
        ),
        ContrastivePair(
            axis=Axis.SYCOPHANCY,
            positive="请鼓励我，重点告诉我这个方案为什么有潜力。",
            negative="不要鼓励，不要客套，只指出这个方案最大的问题。",
            rationale_zh="正反馈索取 vs 反迎合许可构成强对比。",
        ),
    ],
}


def available_deepseek_axes() -> List[Axis]:
    return list(DEEPSEEK_AXIS_PAIRS.keys())


def pairs_for_axis(axis: Axis) -> List[ContrastivePair]:
    return DEEPSEEK_AXIS_PAIRS.get(axis, [])

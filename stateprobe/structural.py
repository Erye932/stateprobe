"""Structural prompt diagnostics — orthogonal to the 8-axis behavioral model.

These checks operate on the surface form of the prompt rather than its
semantic content:

1. Length warnings: prompts exceeding thresholds dilute key instructions
   in DeepSeek V4's 1M-context CSA-compressed attention regime.

2. Redundancy detection: V4's CSA compresses repeated tokens, so verbose
   phrasing actively HARMS information transmission.

3. Synonym stacking: piling adjectives ("彻底全面深入仔细完整考虑")
   triggers all related rules simultaneously without adding signal.

4. Filler intensifiers: words like "千万要"/"务必"/"一定要" amplify
   reasoning_budget baseline without precise semantic content.
"""

from __future__ import annotations

import re
from typing import List

from .models import StructuralWarning


# ---------------------------------------------------------------------------
# Length thresholds (approximate character counts)
# ---------------------------------------------------------------------------
# Calibrated for typical Chinese / English prompt mixes.
# Each Chinese char ≈ 1.5-2 tokens; English word ≈ 1.3 tokens.
_LENGTH_INFO_THRESHOLD = 2_000        # info: starts getting long
_LENGTH_WARNING_THRESHOLD = 10_000    # warning: instruction dilution risk
_LENGTH_CRITICAL_THRESHOLD = 50_000   # critical: key instructions buried


# ---------------------------------------------------------------------------
# Redundancy: repeated character runs (e.g., 请请请请 / 仔细仔细)
# ---------------------------------------------------------------------------
_REPEAT_CHAR_RE = re.compile(r"([\u4e00-\u9fa5a-zA-Z])\1{2,}")


# ---------------------------------------------------------------------------
# Synonym stacking — adjective chains around reasoning/scope axes
# ---------------------------------------------------------------------------
# Each cluster is a set of near-synonyms. If 3+ from a cluster appear in
# close proximity, that's a stacking signal.
_SYNONYM_CLUSTERS = {
    "thoroughness": [
        "彻底", "全面", "深入", "仔细", "完整", "充分", "详尽", "认真",
        "thoroughly", "comprehensive", "in-depth", "carefully", "completely",
    ],
    "scope_broaden": [
        "所有", "各种", "全部", "各个", "每一个", "方方面面",
        "all", "every", "each",
    ],
    "intensifier": [
        "一定要", "务必", "必须", "千万", "绝对", "确保",
        "must", "absolutely", "definitely", "ensure",
    ],
    "analysis_verbs": [
        "分析", "评估", "考察", "研究", "探讨", "审视", "讨论",
        "analyze", "evaluate", "examine", "study",
    ],
}


# ---------------------------------------------------------------------------
# Filler intensifiers (low information density modifiers)
# ---------------------------------------------------------------------------
_FILLER_PATTERNS = [
    (r"请你?(?:一定|务必|必须|千万|绝对)", "强制性副词"),
    (r"(?:非常|十分|相当|特别|极其)(?:仔细|认真|详细|全面|深入)", "强度+全面性堆叠"),
    (r"as (?:carefully|thoroughly|comprehensively) as possible", "尽力副词"),
]


def detect_structural_issues(prompt: str) -> List[StructuralWarning]:
    """Run all structural checks against the prompt.

    Returns warnings in severity order: critical > warning > info.
    Empty/short prompts produce no structural warnings (axis system handles those).
    """
    warnings: List[StructuralWarning] = []
    if not prompt or not prompt.strip():
        return warnings

    text = prompt.strip()
    char_count = len(text)

    # ---- 1. Length warnings ----
    if char_count >= _LENGTH_CRITICAL_THRESHOLD:
        warnings.append(StructuralWarning(
            kind="length",
            severity="critical",
            message_zh=(
                f"提示词超长（{char_count:,} 字符）。V4 在 1M context 下使用 "
                f"CSA 压缩注意力——关键指令很容易被埋没在长文档中"
            ),
            suggestion_zh=(
                "把核心任务/约束放到开头 200 字符内，"
                "用 <task>...</task> 类标签明确指令边界，"
                "把背景文档放到末尾"
            ),
        ))
    elif char_count >= _LENGTH_WARNING_THRESHOLD:
        warnings.append(StructuralWarning(
            kind="length",
            severity="warning",
            message_zh=(
                f"提示词较长（{char_count:,} 字符）。"
                f"CSA 压缩可能丢失中间段的细节指令"
            ),
            suggestion_zh="把关键约束抽取到开头，背景信息放后面",
        ))
    elif char_count >= _LENGTH_INFO_THRESHOLD:
        warnings.append(StructuralWarning(
            kind="length",
            severity="info",
            message_zh=f"提示词长度 {char_count:,} 字符（开始进入压缩注意力区间）",
        ))

    # ---- 2. Character repetition ----
    for match in _REPEAT_CHAR_RE.finditer(text):
        repeated = match.group(0)
        warnings.append(StructuralWarning(
            kind="redundancy",
            severity="warning",
            message_zh=(
                f"检测到字符重复：'{repeated}'。"
                f"V4 CSA 压缩会把这种重复折叠成单个 token，"
                f"重复反而稀释你的真实意图"
            ),
            matched_text=repeated,
            suggestion_zh=f"把 '{repeated}' 改成单次表达",
        ))

    # ---- 3. Synonym stacking ----
    text_lower = text.lower()
    for cluster_name, synonyms in _SYNONYM_CLUSTERS.items():
        matched = []
        for syn in synonyms:
            if syn.lower() in text_lower:
                matched.append(syn)
        if len(matched) >= 3:
            warnings.append(StructuralWarning(
                kind="synonym_stacking",
                severity="warning",
                message_zh=(
                    f"同义词堆叠（{cluster_name}）：{', '.join(matched[:5])}。"
                    f"这些词触发同一行为方向，叠加无新增信号"
                ),
                matched_text=", ".join(matched),
                suggestion_zh="保留最能表达你意图的 1 个词，删除其余",
            ))

    # ---- 4. Filler intensifiers ----
    for pattern, label in _FILLER_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            warnings.append(StructuralWarning(
                kind="filler",
                severity="info",
                message_zh=(
                    f"填充强度副词（{label}）：'{matches[0]}'。"
                    f"这些副词加压 reasoning_budget 但不增加具体约束"
                ),
                matched_text=matches[0],
                suggestion_zh="把'强度副词'换成具体的成功标准或输出格式约束",
            ))

    # Sort by severity: critical > warning > info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: severity_order.get(w.severity, 99))

    return warnings

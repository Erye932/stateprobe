"""StateProbe Skill — Agent 注意力仪表盘 (task-level attention HUD).

Phase 1 公开能力：

- `analyze_attention(user_context, agent_output) -> AttentionHUD`

注意：这一层是「任务注意力」——基于用户上下文和输出文本重建。
它不是神经注意力；神经层证据由未来的企业 Runtime Probe 提供。
"""

from stateprobe.skill.attention import (
    AttentionGap,
    AttentionHUD,
    AttentionPreview,
    AttentionSignal,
    ActivationDecision,
    BoundaryDecomposition,
    BoundaryItem,
    BoundaryOption,
    BoundaryQuestion,
    ContextContaminationRisk,
    ControlLevers,
    IntentSignal,
    LiteralizationRisk,
    OutputTrajectory,
    Requirement,
    RequirementCoverage,
    analyze_attention,
    extract_requirements,
    preview_attention,
)

__all__ = [
    "AttentionGap",
    "AttentionHUD",
    "AttentionPreview",
    "AttentionSignal",
    "ActivationDecision",
    "BoundaryDecomposition",
    "BoundaryItem",
    "BoundaryOption",
    "BoundaryQuestion",
    "ContextContaminationRisk",
    "ControlLevers",
    "IntentSignal",
    "LiteralizationRisk",
    "OutputTrajectory",
    "Requirement",
    "RequirementCoverage",
    "analyze_attention",
    "extract_requirements",
    "preview_attention",
]

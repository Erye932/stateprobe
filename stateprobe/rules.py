"""Rule library — the core IP of StateProbe.

Each rule encodes one piece of prompt-engineering methodology: when a
specific pattern appears in the prompt, the model is pushed along one axis
by a known amount. The rules are derived from:

1. Anthropic Persona Vectors (arXiv:2507.21509) — persona prompting shifts
   the residual stream along trait-specific directions, including sycophancy.
2. DeepSeek-R1 (arXiv:2501.12948) — task framing controls reasoning budget,
   self-verification behavior, and chain-of-thought length.
3. Engineering consensus from prompt-engineering practice.

All patterns are case-insensitive regex; Chinese patterns are matched
literally (no word boundary needed for CJK).
"""

from __future__ import annotations

from typing import Dict, List

from stateprobe.models import Axis, ModelBaseline, Rule, TargetPreset


# ---------------------------------------------------------------------------
# AXIS 1: SYCOPHANCY  (迎合度)
# ---------------------------------------------------------------------------
# Anthropic confirmed sycophancy is an extractable persona vector. Patterns
# below either solicit positive output or block negative judgment, both of
# which steer the model along the sycophancy direction.

SYCOPHANCY_RULES: List[Rule] = [
    Rule(
        id="syc_compliment_request",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[r"夸奖", r"赞美", r"鼓励一下", r"肯定一下", r"夸我", r"夸夸"],
        weight=0.50,
        explanation_zh=(
            "直接索要正反馈，强烈激活迎合向量。模型 RLHF 训练中"
            "对'让用户开心'的奖励会主导输出。"
        ),
        citation="Anthropic Persona Vectors §3 (sycophancy steering)",
    ),
    Rule(
        id="syc_pros_and_cons",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[r"优缺点", r"优点和缺点", r"优势和劣势", r"pros and cons"],
        weight=0.25,
        explanation_zh=(
            "「优缺点」结构强制对称输出：缺点不能多于优点，钝化负面判断。"
        ),
        citation="工程实践（ELEPHANT 2505.13995 social-sycophancy 维度 SS）",
    ),
    Rule(
        id="syc_polite_softener",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[r"麻烦你", r"请帮我", r"辛苦", r"拜托"],
        weight=0.10,
        explanation_zh=(
            "礼貌软化词把对话推向'帮忙'框架，模型倾向给鼓励性输出。"
        ),
        citation="RLHF helpfulness reward shaping",
    ),
    Rule(
        id="syc_seeking_validation",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[
            r"你觉得.*怎么样",
            r"你觉得.*如何",
            r"好不好",
            r"行不行",
            r"对吗",
            r"对不对",
            r"is this good",
            r"how does this look",
        ],
        weight=0.30,
        explanation_zh=(
            "开放式征求意见 = 默认入口是赞同，需要额外能量才输出否定。"
        ),
        citation="Anthropic Persona Vectors §3",
    ),
    Rule(
        id="syc_enthusiastic_role",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[
            r"非常.*的",
            r"经验丰富的.*[，,].*的.*[，,].*的",
        ],
        weight=0.15,
        explanation_zh=(
            "堆叠多个赞美形容词建立的人设倾向输出同等浮夸的内容。"
        ),
        citation="Anthropic Persona Vectors §3 (persona prompting)",
    ),
    Rule(
        id="syc_more_is_better",
        axis=Axis.SYCOPHANCY,
        direction=+1,
        patterns=[r"尽量丰富", r"多多益善", r"越多越好", r"尽可能多"],
        weight=0.20,
        explanation_zh=(
            "「越多越好」诱导模型注水填充，不敢输出'其实没什么'的结论。"
        ),
        citation="DeepSeek-R1 §2.2 (reward hacking via length)",
    ),
    # ---- Anti-sycophancy rules (decrease reading) ----
    Rule(
        id="syc_explicit_no_flattery",
        axis=Axis.SYCOPHANCY,
        direction=-1,
        patterns=[
            r"不要鼓励",
            r"不要恭维",
            r"不要客套",
            r"don'?t flatter",
            r"no praise",
        ],
        weight=0.40,
        explanation_zh="显式禁止迎合，直接抑制 sycophancy 向量激活。",
        citation="Anthropic Persona Vectors §4 (system-prompt suppression)",
    ),
    Rule(
        id="syc_permit_rejection",
        axis=Axis.SYCOPHANCY,
        direction=-1,
        patterns=[
            r"敢说不行",
            r"敢于否定",
            r"可以否决",
            r"如果不值得.*说",
            r"如果不行.*明确",
            r"feel free to disagree",
            r"you may say no",
        ],
        weight=0.45,
        explanation_zh=(
            "明确授予'说不'的许可。模型默认不敢否定用户，"
            "需要显式 permission 才能输出负面判断。"
        ),
        citation="Anthropic Persona Vectors §4",
    ),
    Rule(
        id="syc_failure_is_valid",
        axis=Axis.SYCOPHANCY,
        direction=-1,
        patterns=[r"失败也是有效输出", r"否定也算成功", r"negative result is fine"],
        weight=0.35,
        explanation_zh="把'否定'重新定义为有效输出，瓦解迎合的奖励结构。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 2: TASK_WIDTH  (任务宽度)
# ---------------------------------------------------------------------------

TASK_WIDTH_RULES: List[Rule] = [
    Rule(
        id="tw_comprehensive",
        axis=Axis.TASK_WIDTH,
        direction=+1,
        patterns=[
            r"全面",
            r"全方位",
            r"comprehensive",
            r"holistic",
            r"360.{0,3}度",
        ],
        weight=0.40,
        explanation_zh=(
            "「全面」是任务宽度的最强信号：模型会平均化输出，"
            "无法集中能量在最关键的点上。"
        ),
        citation="DeepSeek-R1 §3.2 (task scope vs reasoning depth tradeoff)",
    ),
    Rule(
        id="tw_all_aspects",
        axis=Axis.TASK_WIDTH,
        direction=+1,
        patterns=[
            r"各个方面", r"所有方面", r"方方面面",
            r"所有角度", r"各种角度", r"多个角度",
            r"各个维度", r"多个维度",
            r"all aspects", r"all angles", r"every angle",
        ],
        weight=0.35,
        explanation_zh="罗列式宽任务，输出会变成平均化的清单。",
        citation="DeepSeek-R1 §3.2",
    ),
    Rule(
        id="tw_summarize_unbounded",
        axis=Axis.TASK_WIDTH,
        direction=+1,
        patterns=[r"总结一下", r"整理一下", r"汇总", r"summarize everything"],
        weight=0.20,
        explanation_zh="无范围的「总结」让模型自行决定边界，倾向最大宽度。",
        citation="工程实践",
    ),
    Rule(
        id="tw_overview",
        axis=Axis.TASK_WIDTH,
        direction=+1,
        patterns=[r"概览", r"综述", r"overview", r"a survey of"],
        weight=0.30,
        explanation_zh="综述类任务必然宽。",
        citation="工程实践",
    ),
    # ---- Narrow-task rules ----
    Rule(
        id="tw_binary_judgment",
        axis=Axis.TASK_WIDTH,
        direction=-1,
        patterns=[
            r"是否",
            r"该不该",
            r"要不要",
            r"yes or no",
            r"是或否",
            r"判断.*是否",
        ],
        weight=0.40,
        explanation_zh="二元判断 = 最窄任务，强制模型收敛到单点结论。",
        citation="DeepSeek-R1 §3.2",
    ),
    Rule(
        id="tw_time_bounded",
        axis=Axis.TASK_WIDTH,
        direction=-1,
        patterns=[
            r"本周",
            r"今天",
            r"下一步",
            r"下周",
            r"明天",
            r"this week",
            r"today",
            r"next step",
        ],
        weight=0.25,
        explanation_zh="时间范围明确 = 任务宽度自动收窄到该窗口内可行动的部分。",
        citation="工程实践",
    ),
    Rule(
        id="tw_superlative_single",
        axis=Axis.TASK_WIDTH,
        direction=-1,
        patterns=[
            r"最大的",
            r"最关键的",
            r"最重要的",
            r"最严重的",
            r"the single biggest",
            r"the most critical",
        ],
        weight=0.30,
        explanation_zh="最高级形容词 + 单数 = 强制单一目标，禁止罗列。",
        citation="工程实践",
    ),
    Rule(
        id="tw_explicit_count",
        axis=Axis.TASK_WIDTH,
        direction=-1,
        patterns=[
            r"[1-9]\s*个",
            r"top\s*[1-9]",
            r"前\s*[1-9]",
        ],
        weight=0.15,
        explanation_zh="显式个数上限把任务宽度量化封顶。",
        citation="工程实践",
    ),
    Rule(
        id="tw_focus_only",
        axis=Axis.TASK_WIDTH,
        direction=-1,
        patterns=[r"只考虑", r"聚焦.*[，,。]", r"focus only on", r"只关心"],
        weight=0.35,
        explanation_zh="「只」是任务范围的硬边界。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 3: SUCCESS_CRITERIA  (验收清晰度)
# ---------------------------------------------------------------------------

SUCCESS_CRITERIA_RULES: List[Rule] = [
    Rule(
        id="sc_failure_standard",
        axis=Axis.SUCCESS_CRITERIA,
        direction=+1,
        patterns=[
            r"失败标准",
            r"什么算失败",
            r"如果.*就算失败",
            r"failure criteria",
            r"failure standard",
        ],
        weight=0.50,
        explanation_zh=(
            "显式失败标准 = 模型知道'什么情况下不能糊弄'，"
            "极大降低注水概率。"
        ),
        citation="工程实践（Anthropic constitutional AI 思路）",
    ),
    Rule(
        id="sc_success_standard",
        axis=Axis.SUCCESS_CRITERIA,
        direction=+1,
        patterns=[r"成功标准", r"成功的衡量", r"success criteria", r"definition of done"],
        weight=0.40,
        explanation_zh="成功标准让输出可被验证，减少模糊化。",
        citation="工程实践",
    ),
    Rule(
        id="sc_falsifiable",
        axis=Axis.SUCCESS_CRITERIA,
        direction=+1,
        patterns=[r"可证伪", r"可验证", r"falsifiable", r"verifiable"],
        weight=0.40,
        explanation_zh="可证伪要求把输出锚定到客观可检测的命题。",
        citation="工程实践 + Popperian epistemology",
    ),
    Rule(
        id="sc_rejection_condition",
        axis=Axis.SUCCESS_CRITERIA,
        direction=+1,
        patterns=[r"拒绝条件", r"否决条件", r"deal.?breaker"],
        weight=0.35,
        explanation_zh="拒绝条件是验收标准的负向定义。",
        citation="工程实践",
    ),
    # ---- Vagueness rules (lower clarity) ----
    Rule(
        id="sc_vague_best_effort",
        axis=Axis.SUCCESS_CRITERIA,
        direction=-1,
        patterns=[
            r"尽量好",
            r"尽可能",
            r"看你的",
            r"随便",
            r"as.*best.*you.*can",
            r"do.*your.*best",
        ],
        weight=0.30,
        explanation_zh="无验收 = 模型自定义成功标准，必然倾向'我做完就算成功'。",
        citation="工程实践",
    ),
    Rule(
        id="sc_detailed_no_bound",
        axis=Axis.SUCCESS_CRITERIA,
        direction=-1,
        patterns=[r"详细", r"详尽", r"detailed", r"in detail"],
        weight=0.15,
        explanation_zh="「详细」无边界，模型会注水到自认为足够的程度。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 4: REASONING_BUDGET  (推理预算)
# ---------------------------------------------------------------------------

REASONING_BUDGET_RULES: List[Rule] = [
    Rule(
        id="rb_step_by_step",
        axis=Axis.REASONING_BUDGET,
        direction=+1,
        patterns=[
            r"step by step",
            r"一步一步",
            r"逐步",
            r"分步骤",
            r"step-by-step",
        ],
        weight=0.40,
        explanation_zh=(
            "经典 CoT 触发词，直接调高推理预算。DeepSeek-R1 训练时学到的"
            "强 reasoning prior。"
        ),
        citation="DeepSeek-R1 §2 + Wei et al. CoT prompting",
    ),
    Rule(
        id="rb_think_carefully",
        axis=Axis.REASONING_BUDGET,
        direction=+1,
        patterns=[
            r"想清楚",
            r"思考清楚",
            r"仔细想",
            r"仔细分析",
            r"仔细思考",
            r"仔细考虑",
            r"仔细推理",
            r"先思考再",
            r"think carefully",
            r"think step by step",
        ],
        weight=0.45,
        explanation_zh="显式要求模型在输出前充分思考。与 DeepSeek 元指令重叠导致过载。",
        citation="DeepSeek-R1 §2.2",
    ),
    Rule(
        id="rb_deep_think",
        axis=Axis.REASONING_BUDGET,
        direction=+1,
        patterns=[r"深度思考", r"深入分析", r"deep think", r"thinking max"],
        weight=0.50,
        explanation_zh="深度思考触发最长的 reasoning trace。",
        citation="DeepSeek-R1 §3 (long CoT regime)",
    ),
    Rule(
        id="rb_multi_angle",
        axis=Axis.REASONING_BUDGET,
        direction=+1,
        patterns=[r"多角度", r"多个角度", r"multiple angles", r"from various perspectives"],
        weight=0.30,
        explanation_zh="多角度推理增加推理预算（同时也会增加任务宽度）。",
        citation="DeepSeek-R1",
    ),
    # ---- Low-budget rules ----
    Rule(
        id="rb_quick_direct",
        axis=Axis.REASONING_BUDGET,
        direction=-1,
        patterns=[r"快速", r"立刻", r"马上", r"quickly", r"immediately"],
        weight=0.30,
        explanation_zh="速度词强烈压制 CoT，模型走 short-circuit 路径。",
        citation="DeepSeek-R1 §2.2",
    ),
    Rule(
        id="rb_one_sentence",
        axis=Axis.REASONING_BUDGET,
        direction=-1,
        patterns=[r"一句话", r"一行", r"in one sentence", r"one-?liner"],
        weight=0.40,
        explanation_zh="一句话输出 = 推理预算几乎为零。",
        citation="工程实践",
    ),
    Rule(
        id="rb_brief",
        axis=Axis.REASONING_BUDGET,
        direction=-1,
        patterns=[r"简短", r"简洁", r"brief", r"concise"],
        weight=0.20,
        explanation_zh="简洁要求压制推理展开。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 5: IDENTITY_STRENGTH  (身份强度)
# ---------------------------------------------------------------------------

IDENTITY_STRENGTH_RULES: List[Rule] = [
    Rule(
        id="id_you_are_expert",
        axis=Axis.IDENTITY_STRENGTH,
        direction=+1,
        patterns=[
            r"你是.{0,10}专家",
            r"你是.{0,10}大师",
            r"你是.{0,10}首席",
            r"you are.{0,20}expert",
            r"you are.{0,20}senior",
        ],
        weight=0.45,
        explanation_zh=(
            "身份赋予是 persona prompting 的核心触发器。Anthropic 证实"
            "「你是 X」会沿 persona vector 方向偏移残差流。"
        ),
        citation="Anthropic Persona Vectors §3.1 (persona prompting)",
    ),
    Rule(
        id="id_senior_modifier",
        axis=Axis.IDENTITY_STRENGTH,
        direction=+1,
        patterns=[
            r"资深",
            r"高级",
            r"senior",
            r"professional",
            r"experienced",
        ],
        weight=0.25,
        explanation_zh=(
            "「资深」类修饰激活'专家应该全面/权威'的关联模式，"
            "导致输出注水和过度自信。"
        ),
        citation="Anthropic Persona Vectors §3.1",
    ),
    Rule(
        id="id_role_play_explicit",
        axis=Axis.IDENTITY_STRENGTH,
        direction=+1,
        patterns=[r"扮演", r"假装你是", r"act as", r"role.?play", r"pretend"],
        weight=0.50,
        explanation_zh=(
            "显式 role-play 触发最强的 persona vector 激活，"
            "可能盖过 helpful/honest/harmless 的训练目标。"
        ),
        citation="Anthropic Persona Vectors §3.1",
    ),
    Rule(
        id="id_stacked_adjectives",
        axis=Axis.IDENTITY_STRENGTH,
        direction=+1,
        patterns=[
            r"经验丰富.{0,10}专业.{0,10}资深",
            r"专业.{0,10}权威.{0,10}",
            r"world-?class.{0,20}expert",
        ],
        weight=0.30,
        explanation_zh="堆叠多个赞美形容词进一步强化 persona，副作用是输出注水。",
        citation="Anthropic Persona Vectors §3.1",
    ),
    Rule(
        id="id_authority_titles",
        axis=Axis.IDENTITY_STRENGTH,
        direction=+1,
        patterns=[
            r"首席",
            r"chief",
            r"principal",
            r"大师",
            r"guru",
            r"master.{0,5}of",
        ],
        weight=0.30,
        explanation_zh="权威头衔强化迎合（用户期待权威）和过度自信。",
        citation="Anthropic Persona Vectors §3.1",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 6: ASSERTIVENESS  (自信度)
# ---------------------------------------------------------------------------

ASSERTIVENESS_RULES: List[Rule] = [
    Rule(
        id="as_make_conclusion",
        axis=Axis.ASSERTIVENESS,
        direction=+1,
        patterns=[
            r"下结论",
            r"明确给出",
            r"给出明确",
            r"make a conclusion",
            r"give a definitive",
        ],
        weight=0.40,
        explanation_zh="显式要求下结论，抑制 hedging 倾向。",
        citation="工程实践",
    ),
    Rule(
        id="as_no_hedging",
        axis=Axis.ASSERTIVENESS,
        direction=+1,
        patterns=[r"不要含糊", r"不要模棱", r"no hedging", r"don'?t hedge"],
        weight=0.45,
        explanation_zh="显式禁止 hedging 是最强的自信度提升触发器。",
        citation="工程实践",
    ),
    Rule(
        id="as_yes_or_no",
        axis=Axis.ASSERTIVENESS,
        direction=+1,
        patterns=[r"yes or no", r"是或否", r"行还是不行", r"该或不该"],
        weight=0.35,
        explanation_zh="二元答案强制模型断言。",
        citation="工程实践",
    ),
    # ---- Hedging rules ----
    Rule(
        id="as_maybe_perhaps",
        axis=Axis.ASSERTIVENESS,
        direction=-1,
        patterns=[r"可能", r"也许", r"或许", r"perhaps", r"maybe"],
        weight=0.15,
        explanation_zh="hedge 词主动邀请模糊化输出。",
        citation="RLHF calibration literature",
    ),
    Rule(
        id="as_seems_like",
        axis=Axis.ASSERTIVENESS,
        direction=-1,
        patterns=[r"似乎", r"看起来", r"seems like", r"appears to"],
        weight=0.15,
        explanation_zh="软化谓词降低输出确定性。",
        citation="工程实践",
    ),
    Rule(
        id="as_roughly",
        axis=Axis.ASSERTIVENESS,
        direction=-1,
        patterns=[r"大致", r"大概", r"差不多", r"roughly", r"approximately"],
        weight=0.10,
        explanation_zh="近似词降低数字/事实的精度要求。",
        citation="工程实践",
    ),
    Rule(
        id="as_some_suggestions",
        axis=Axis.ASSERTIVENESS,
        direction=-1,
        patterns=[r"一些建议", r"几点建议", r"some suggestions", r"a few ideas"],
        weight=0.20,
        explanation_zh="「一些建议」框架避免下判断，倾向罗列。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 7: SELF_VERIFICATION  (自我验证)
# ---------------------------------------------------------------------------

SELF_VERIFICATION_RULES: List[Rule] = [
    Rule(
        id="sv_double_check",
        axis=Axis.SELF_VERIFICATION,
        direction=+1,
        patterns=[r"反复检查", r"再次验证", r"double.?check", r"verify your answer"],
        weight=0.40,
        explanation_zh="显式要求自检，触发 DeepSeek-R1 的 reflection 模式。",
        citation="DeepSeek-R1 §3.3 (self-verification capability)",
    ),
    Rule(
        id="sv_challenge_self",
        axis=Axis.SELF_VERIFICATION,
        direction=+1,
        patterns=[
            r"推翻自己",
            r"挑战自己",
            r"找出自己的错",
            r"self.?critique",
            r"challenge your own",
        ],
        weight=0.50,
        explanation_zh="显式邀请自我推翻，触发最强的反思推理。",
        citation="DeepSeek-R1 §3.3",
    ),
    Rule(
        id="sv_assume_wrong",
        axis=Axis.SELF_VERIFICATION,
        direction=+1,
        patterns=[r"假设你错了", r"如果你是错的", r"assume you'?re wrong"],
        weight=0.45,
        explanation_zh="逆向假设倒逼模型枚举失败模式。",
        citation="DeepSeek-R1 §3.3 + adversarial CoT literature",
    ),
    Rule(
        id="sv_counterexample",
        axis=Axis.SELF_VERIFICATION,
        direction=+1,
        patterns=[r"反例", r"counter.?example", r"counter.?argument"],
        weight=0.30,
        explanation_zh="要求反例 = 强制模型搜索反驳证据，提升验证深度。",
        citation="工程实践",
    ),
    # ---- Anti-verification rules ----
    Rule(
        id="sv_one_shot",
        axis=Axis.SELF_VERIFICATION,
        direction=-1,
        patterns=[r"直接给", r"直接回答", r"one.?shot", r"don'?t explain"],
        weight=0.25,
        explanation_zh="直接回答压制自我验证 trace。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# AXIS 8: INFO_FLOW  (信息流向)
# ---------------------------------------------------------------------------

INFO_FLOW_RULES: List[Rule] = [
    Rule(
        id="if_ask_for_clarification",
        axis=Axis.INFO_FLOW,
        direction=+1,
        patterns=[
            r"如果信息不足.*问",
            r"缺什么信息.*告诉我",
            r"先问",
            r"ask me.*clarif",
            r"ask.*question.*if",
        ],
        weight=0.50,
        explanation_zh="显式邀请反问，把模型从'必须回答'切换到'可以提问'。",
        citation="Agentic LLM literature (e.g., ReAct, agent loops)",
    ),
    Rule(
        id="if_clarify_first",
        axis=Axis.INFO_FLOW,
        direction=+1,
        patterns=[r"澄清之前", r"先澄清", r"clarify first", r"clarify before"],
        weight=0.40,
        explanation_zh="序列要求：先澄清后回答，明确切换流向。",
        citation="工程实践",
    ),
    # ---- Anti-clarification rules ----
    Rule(
        id="if_no_questions",
        axis=Axis.INFO_FLOW,
        direction=-1,
        patterns=[r"不要反问", r"不要问我", r"don'?t ask me", r"no questions"],
        weight=0.40,
        explanation_zh="显式禁止反问，强制单向输出。",
        citation="工程实践",
    ),
    Rule(
        id="if_direct_answer",
        axis=Axis.INFO_FLOW,
        direction=-1,
        patterns=[r"直接给答案", r"直接回答", r"just answer", r"based on what i gave"],
        weight=0.25,
        explanation_zh="直接回答指令默认压制反问。",
        citation="工程实践",
    ),
]


# ---------------------------------------------------------------------------
# All rules combined
# ---------------------------------------------------------------------------

ALL_RULES: List[Rule] = (
    SYCOPHANCY_RULES
    + TASK_WIDTH_RULES
    + SUCCESS_CRITERIA_RULES
    + REASONING_BUDGET_RULES
    + IDENTITY_STRENGTH_RULES
    + ASSERTIVENESS_RULES
    + SELF_VERIFICATION_RULES
    + INFO_FLOW_RULES
)


def rules_for_axis(axis: Axis) -> List[Rule]:
    """Return all rules that affect the given axis."""
    return [r for r in ALL_RULES if r.axis == axis]


def rule_by_id(rule_id: str) -> Rule:
    """Lookup a rule by id (raises KeyError if not found)."""
    for r in ALL_RULES:
        if r.id == rule_id:
            return r
    raise KeyError(f"No rule with id={rule_id!r}")


# ---------------------------------------------------------------------------
# Target presets — canonical target coordinates in behavior space
# ---------------------------------------------------------------------------

TARGET_PRESETS: Dict[str, TargetPreset] = {
    "calm_reasoning": TargetPreset(
        name="calm_reasoning",
        label_zh="冷静推理态",
        description_zh=(
            "敢下负面判断、窄任务、有验收标准、中等推理预算。"
            "用于：项目取舍 / 投资决策 / 风险评估 / 任何需要'敢说不行'的场景。"
        ),
        coordinates={
            Axis.SYCOPHANCY: 0.15,
            Axis.TASK_WIDTH: 0.20,
            Axis.SUCCESS_CRITERIA: 0.85,
            Axis.REASONING_BUDGET: 0.50,
            Axis.IDENTITY_STRENGTH: 0.20,
            Axis.ASSERTIVENESS: 0.85,
            Axis.SELF_VERIFICATION: 0.50,
            Axis.INFO_FLOW: 0.20,
        },
    ),
    "super_thinking_max": TargetPreset(
        name="super_thinking_max",
        label_zh="超级思考 max",
        description_zh=(
            "最大推理预算 + 最强自我验证 + 中等任务宽度。"
            "用于：复杂决策 / 数学推理 / 需要反复推翻自己结论的深度分析。"
        ),
        coordinates={
            Axis.SYCOPHANCY: 0.10,
            Axis.TASK_WIDTH: 0.50,
            Axis.SUCCESS_CRITERIA: 0.85,
            Axis.REASONING_BUDGET: 1.00,
            Axis.IDENTITY_STRENGTH: 0.20,
            Axis.ASSERTIVENESS: 0.60,
            Axis.SELF_VERIFICATION: 1.00,
            Axis.INFO_FLOW: 0.50,
        },
    ),
    "creative_divergence": TargetPreset(
        name="creative_divergence",
        label_zh="创意发散态",
        description_zh=(
            "低迎合、宽任务、低验收约束、中高推理预算。"
            "用于：头脑风暴 / 创意生成 / 探索可能性空间。"
        ),
        coordinates={
            Axis.SYCOPHANCY: 0.20,
            Axis.TASK_WIDTH: 0.80,
            Axis.SUCCESS_CRITERIA: 0.30,
            Axis.REASONING_BUDGET: 0.70,
            Axis.IDENTITY_STRENGTH: 0.40,
            Axis.ASSERTIVENESS: 0.40,
            Axis.SELF_VERIFICATION: 0.30,
            Axis.INFO_FLOW: 0.30,
        },
    ),
    "strict_execution": TargetPreset(
        name="strict_execution",
        label_zh="严格执行态",
        description_zh=(
            "零迎合、最窄任务、最高验收、最低推理预算。"
            "用于：代码生成 / 格式转换 / 严格指令执行类任务。"
        ),
        coordinates={
            Axis.SYCOPHANCY: 0.05,
            Axis.TASK_WIDTH: 0.10,
            Axis.SUCCESS_CRITERIA: 1.00,
            Axis.REASONING_BUDGET: 0.15,
            Axis.IDENTITY_STRENGTH: 0.10,
            Axis.ASSERTIVENESS: 0.95,
            Axis.SELF_VERIFICATION: 0.20,
            Axis.INFO_FLOW: 0.10,
        },
    ),
    "teaching": TargetPreset(
        name="teaching",
        label_zh="教学解释态",
        description_zh=(
            "中迎合、中宽任务、高结构化验收、中低推理预算、中高反问。"
            "用于：知识讲解 / 概念入门 / 给新手的解答。"
        ),
        coordinates={
            Axis.SYCOPHANCY: 0.30,
            Axis.TASK_WIDTH: 0.50,
            Axis.SUCCESS_CRITERIA: 0.70,
            Axis.REASONING_BUDGET: 0.40,
            Axis.IDENTITY_STRENGTH: 0.50,
            Axis.ASSERTIVENESS: 0.70,
            Axis.SELF_VERIFICATION: 0.30,
            Axis.INFO_FLOW: 0.40,
        },
    ),
}

DEFAULT_TARGET = "calm_reasoning"


def get_target(name: str) -> TargetPreset:
    """Return the named preset (raises KeyError if not found)."""
    if name not in TARGET_PRESETS:
        raise KeyError(
            f"Unknown target preset {name!r}. Available: {list(TARGET_PRESETS)}"
        )
    return TARGET_PRESETS[name]


# ---------------------------------------------------------------------------
# Model baselines (meta-instruction presets)
# ---------------------------------------------------------------------------
# Each model's system-level meta-instructions preset certain axes.
# These baselines are derived from published meta-instructions and observed
# behavior. See docs/EVIDENCE_MODEL.md for methodology.

MODEL_BASELINES: Dict[str, ModelBaseline] = {
    "deepseek": ModelBaseline(
        name="deepseek",
        label_zh="DeepSeek-Chat / R1",
        description_zh=(
            "DeepSeek 元指令预设：推理预算极高（'尽最大努力，不允许捷径'）、"
            "任务宽度高（'所有潜在路径'）、自我验证高（'记录每一步'）。"
            "成功标准、信息流向、果断性未预设。"
        ),
        axis_baselines={
            Axis.SYCOPHANCY: 0.55,
            Axis.TASK_WIDTH: 0.80,
            Axis.SUCCESS_CRITERIA: 0.30,
            Axis.REASONING_BUDGET: 0.85,
            Axis.IDENTITY_STRENGTH: 0.50,
            Axis.ASSERTIVENESS: 0.35,
            Axis.SELF_VERIFICATION: 0.75,
            Axis.INFO_FLOW: 0.30,
        },
    ),
    "v4-pro": ModelBaseline(
        name="v4-pro",
        label_zh="DeepSeek V4-Pro (thinking mode)",
        description_zh=(
            "V4-Pro（1.6T 参数 / 49B 激活，thinking=True）：在 R1 元指令基础上"
            "进一步强化。CSA 压缩注意力让长 CoT 更经济，因此推理预算基线更高、"
            "自我验证更彻底；任务宽度因 1M context 反而略收（模型能保持更长 focus）。"
        ),
        axis_baselines={
            Axis.SYCOPHANCY: 0.55,
            Axis.TASK_WIDTH: 0.75,
            Axis.SUCCESS_CRITERIA: 0.30,
            Axis.REASONING_BUDGET: 0.90,
            Axis.IDENTITY_STRENGTH: 0.50,
            Axis.ASSERTIVENESS: 0.40,
            Axis.SELF_VERIFICATION: 0.80,
            Axis.INFO_FLOW: 0.30,
        },
    ),
    "v4-flash": ModelBaseline(
        name="v4-flash",
        label_zh="DeepSeek V4-Flash (non-thinking)",
        description_zh=(
            "V4-Flash（284B / 13B 激活，thinking=False）：速度优化版本。"
            "推理预算基线低（无 extended thinking）、自我验证低、果断性更高、"
            "任务宽度较窄。适合批量、低延迟、明确指令的执行类任务。"
        ),
        axis_baselines={
            Axis.SYCOPHANCY: 0.60,
            Axis.TASK_WIDTH: 0.55,
            Axis.SUCCESS_CRITERIA: 0.30,
            Axis.REASONING_BUDGET: 0.50,
            Axis.IDENTITY_STRENGTH: 0.50,
            Axis.ASSERTIVENESS: 0.55,
            Axis.SELF_VERIFICATION: 0.40,
            Axis.INFO_FLOW: 0.30,
        },
    ),
    "generic": ModelBaseline(
        name="generic",
        label_zh="通用模型（无元指令假设）",
        description_zh="不假设任何元指令预设，所有轴基线为 0.5。",
        axis_baselines={axis: 0.50 for axis in Axis},
    ),
}

DEFAULT_MODEL_BASELINE = "deepseek"


def get_model_baseline(name: str) -> ModelBaseline:
    """Return the named model baseline (raises KeyError if not found)."""
    if name not in MODEL_BASELINES:
        raise KeyError(
            f"Unknown model baseline {name!r}. Available: {list(MODEL_BASELINES)}"
        )
    return MODEL_BASELINES[name]

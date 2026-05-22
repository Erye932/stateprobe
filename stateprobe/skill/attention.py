"""StateProbe Skill 核心引擎：从用户上下文 + agent 输出，重建任务注意力。

输入
----
- ``user_context``：用户给 agent 的话（可包含多句、可中英混合）。
- ``agent_output``：agent 对应的回答。

输出
----
- :class:`AttentionHUD`：包含核心关注、已体现要求、被弱化要求、被忽略要求、
  被违反要求（用户说「不要 X」但输出里出现 X）、偏移程度、下一轮纠偏提示。

边界
----
- 这是 *任务注意力*：从用户文本和输出文本里看出来的回应程度。
- 它 **不是** 模型内部的真实神经注意力。
- 真实激活观察由未来的企业 Runtime Probe 提供，本模块不做任何那方面的承诺。

工程约束
----------
- 不引入新的依赖（仅用标准库）。
- 不调用 LLM、不读模型权重、不访问网络。
- 中英文都能跑；中文不依赖分词库（用 2/3-gram 近似关键词）。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 标记词：表达「这是硬要求」的触发短语
# ---------------------------------------------------------------------------

# 「必须做 / 重点关注 / 主线」
POSITIVE_MARKERS_ZH: Tuple[str, ...] = (
    "必须", "一定要", "务必", "需要", "要求",
    "重点", "核心", "主线", "重中之重", "优先",
    "只要", "唯一",
)

# 「不要做 / 禁止 / 切忌」
NEGATIVE_MARKERS_ZH: Tuple[str, ...] = (
    "不要", "不能", "不该", "切忌", "千万不要",
    "别", "禁止", "避免", "不是", "并非",
)

POSITIVE_MARKERS_EN: Tuple[str, ...] = (
    "must ", "should ", "need to", "have to",
    "key ", "core ", "main ", "priority", "important",
    "only ",
)

NEGATIVE_MARKERS_EN: Tuple[str, ...] = (
    "must not", "should not", "do not", "don't",
    "never", "avoid", "forbid", "cannot", "can't",
)


# ---------------------------------------------------------------------------
# 停用词（关键词提取时跳过）
# ---------------------------------------------------------------------------

STOPWORDS = {
    # 中文功能字
    "的", "了", "在", "是", "有", "和", "与", "或", "也", "都",
    "就", "还", "你", "我", "他", "她", "它", "这", "那",
    "把", "被", "给", "让", "上", "下", "里", "中",
    "什么", "怎么", "如何", "可以", "可能", "应该",
    "一个", "一些", "这个", "那个",
    # 英文 stopwords
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "of", "to", "in", "on", "for", "by", "with", "as", "at",
    "and", "or", "but", "that", "this", "these", "those",
    "you", "we", "they", "it", "he", "she",
    "do", "does", "did", "have", "has", "had",
    "not", "no",
}

# 句子分隔：中英标点 + 换行
SENTENCE_SPLIT_RE = re.compile(r"[。！？!?;\n]+")
CLAUSE_SPLIT_RE = re.compile(r"[，,、：:]+")

CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
EN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class Requirement:
    """从用户上下文里抽出的一条要求。

    ``polarity`` ∈ {"must", "must_not", "soft"}：

    - ``must``：用户用了正向标记词（必须 / 核心 / must / only…）。
    - ``must_not``：用户用了否定标记词（不要 / 禁止 / never…）。
    - ``soft``：没有标记词，但内容里有实质关键词，用户重复出现就会自动加权。

    ``strength`` 是 0~1 的重要程度。0.9 是硬要求，0.4 是软要求，被
    ``_boost_repeated`` 提权后软要求可以升到 0.7+。
    """

    text: str
    polarity: str
    keywords: List[str]
    strength: float
    marker: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RequirementCoverage:
    """一条要求在 agent 输出里的覆盖情况。

    ``status`` ∈ {"reflected", "weak", "ignored", "violated"}：

    - 正向要求：覆盖率 ≥ 0.6 → reflected；≥ 0.2 → weak；其余 → ignored。
    - 否定要求：输出里出现了被禁止的关键词 → violated；少量命中 → weak；
      完全没出现 → reflected（成功避开）。
    """

    requirement: Requirement
    status: str
    coverage: float
    matched_keywords: List[str]
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "requirement": self.requirement.to_dict(),
            "status": self.status,
            "coverage": self.coverage,
            "matched_keywords": self.matched_keywords,
            "notes": self.notes,
        }


@dataclass
class IntentSignal:
    """用户意图地图里的一条：来自 Requirement，带归一化权重。

    Phase 7 起作为 HUD 的一部分输出，让用户/agent 一眼看到「用户真正要求的
    分布」，再和 ``agent_attention_map`` 对照。
    """

    label: str
    priority: str  # "must" | "must_not" | "supporting"
    weight: float
    evidence: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttentionSignal:
    """Agent 当前注意力地图的一条：从输出文本里重建的关注落点。

    ``alignment``:

    - ``aligned``：命中了 must 要求的关键词，且对应要求被充分回应；
    - ``partial``：命中了 must 要求关键词，但要求只被弱化回应；
    - ``off_task``：未匹配任何 user 要求关键词；
    - ``violation``：命中了 must_not 要求的关键词。
    """

    label: str
    weight: float
    alignment: str
    evidence: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttentionGap:
    """用户意图与 agent 注意力之间的缺口。"""

    label: str
    kind: str  # "missing" | "under_focused" | "over_focused"
    severity: str  # "low" | "medium" | "high"
    why: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OutputTrajectory:
    """按当前注意力分布继续写下去，输出可能变成什么。

    这是一个 *基于词频与覆盖度的启发式预测*；不是模型未来 token 的真实预测。
    """

    likely_direction: str
    risk: str  # "low" | "medium" | "high"
    confidence: str  # "low" | "medium" | "high"
    why: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ControlLevers:
    """下一轮可执行的注意力调节杆。

    - ``boost`` / ``return_to``：要把注意力拉回去的目标；
    - ``suppress`` / ``stop_doing``：要立刻减少或停止的注意力方向。
    """

    boost: List[str]
    suppress: List[str]
    stop_doing: List[str]
    return_to: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ActivationDecision:
    action: str
    should_stop: bool
    reason: str
    message: str
    blockers: List[str]
    next_steps: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttentionHUD:
    """注意力仪表盘：StateProbe Skill 的最终产出。

    Phase 7 起，HUD 不只看「要求是否被回应」，还显示完整闭环：

    - ``user_intent_map``：用户意图地图（要求 + 归一化权重）。
    - ``agent_attention_map``：agent 当前注意力地图（输出文本重建）。
    - ``attention_gaps``：意图与注意力之间的缺口。
    - ``output_trajectory``：如果继续写下去，输出可能变成什么。
    - ``control_levers``：下一轮可执行的 boost / suppress / stop_doing /
      return_to。
    - ``interrupt_level``：是否应当暂停当前输出。

    既有字段（``reflected`` / ``weak`` / ``ignored`` / ``violated`` /
    ``drift_level`` / ``next_turn_patch`` 等）保持不变，是 Phase 7 字段的
    底层证据。
    """

    core_focus: List[str]
    reflected: List[RequirementCoverage]
    weak: List[RequirementCoverage]
    ignored: List[RequirementCoverage]
    violated: List[RequirementCoverage]
    drift_level: str  # "low" | "medium" | "high"
    drift_score: float
    next_turn_patch: List[str]
    notes: List[str] = field(default_factory=list)
    user_intent_map: List[IntentSignal] = field(default_factory=list)
    agent_attention_map: List[AttentionSignal] = field(default_factory=list)
    attention_gaps: List[AttentionGap] = field(default_factory=list)
    output_trajectory: Optional[OutputTrajectory] = None
    control_levers: Optional[ControlLevers] = None
    interrupt_level: str = "ok"  # "ok" | "watch" | "interrupt"

    def to_dict(self) -> Dict:
        return {
            "core_focus": self.core_focus,
            "reflected": [c.to_dict() for c in self.reflected],
            "weak": [c.to_dict() for c in self.weak],
            "ignored": [c.to_dict() for c in self.ignored],
            "violated": [c.to_dict() for c in self.violated],
            "drift_level": self.drift_level,
            "drift_score": self.drift_score,
            "next_turn_patch": self.next_turn_patch,
            "notes": self.notes,
            "user_intent_map": [s.to_dict() for s in self.user_intent_map],
            "agent_attention_map": [
                s.to_dict() for s in self.agent_attention_map
            ],
            "attention_gaps": [g.to_dict() for g in self.attention_gaps],
            "output_trajectory": (
                self.output_trajectory.to_dict()
                if self.output_trajectory
                else None
            ),
            "control_levers": (
                self.control_levers.to_dict() if self.control_levers else None
            ),
            "interrupt_level": self.interrupt_level,
        }


@dataclass
class AttentionPreview:
    user_intent_map: List[IntentSignal]
    planned_attention_map: List[AttentionSignal]
    missing_before_start: List[AttentionGap]
    risk_level: str  # "low" | "medium" | "high"
    risk_score: float
    should_continue: bool
    opening_patch: List[str]
    control_levers: ControlLevers
    activation_decision: ActivationDecision
    boundary_decomposition: Optional["BoundaryDecomposition"] = None
    literalization_risks: List["LiteralizationRisk"] = field(default_factory=list)
    boundary_questions: List["BoundaryQuestion"] = field(default_factory=list)
    context_contamination_risks: List["ContextContaminationRisk"] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "user_intent_map": [s.to_dict() for s in self.user_intent_map],
            "planned_attention_map": [
                s.to_dict() for s in self.planned_attention_map
            ],
            "missing_before_start": [
                g.to_dict() for g in self.missing_before_start
            ],
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "should_continue": self.should_continue,
            "opening_patch": self.opening_patch,
            "control_levers": self.control_levers.to_dict(),
            "activation_decision": self.activation_decision.to_dict(),
            "boundary_decomposition": (
                self.boundary_decomposition.to_dict()
                if self.boundary_decomposition
                else None
            ),
            "literalization_risks": [
                r.to_dict() for r in self.literalization_risks
            ],
            "boundary_questions": [
                q.to_dict() for q in self.boundary_questions
            ],
            "context_contamination_risks": [
                r.to_dict() for r in self.context_contamination_risks
            ],
            "notes": self.notes,
        }


@dataclass
class BoundaryItem:
    """边界分解中的一个元素。

    ``category`` ∈ {"must_show", "can_imply", "must_not_show"}：

    - ``must_show``：用户明确提到的具体实体/物件，画面必须包含。
    - ``can_imply``：动作/状态/抽象概念，可通过暗示表达而非字面渲染。
    - ``must_not_show``：用户明确禁止出现的内容。
    """

    element: str
    category: str  # "must_show" | "can_imply" | "must_not_show"
    reason: str
    source_text: str  # 来自用户 prompt 的原文

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BoundaryDecomposition:
    """prompt 的边界三分类结果。"""

    must_show: List[BoundaryItem]
    can_imply: List[BoundaryItem]
    must_not_show: List[BoundaryItem]

    def to_dict(self) -> Dict:
        return {
            "must_show": [i.to_dict() for i in self.must_show],
            "can_imply": [i.to_dict() for i in self.can_imply],
            "must_not_show": [i.to_dict() for i in self.must_not_show],
        }


@dataclass
class LiteralizationRisk:
    """字面化风险：某个动作/状态会被模型字面渲染，可能不符合用户意图。

    例："打游戏" → 模型会在画面中渲染手机屏幕上的游戏 UI，
    但用户可能只想通过姿态暗示。
    """

    element: str
    literal_interpretation: str  # 模型可能的字面渲染
    risk_description: str  # 为什么这是个风险
    severity: str  # "low" | "medium" | "high"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BoundaryOption:
    """边界反问的一个选项。"""

    label: str  # "A" / "B" / "C"
    description: str
    recommended: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BoundaryQuestion:
    """边界反问：让用户在生成前选择如何处理一个歧义元素。

    例："你是否真的想看到游戏画面？"
    A. 是，屏幕上要有游戏 UI
    B. 不，通过姿态暗示就行（推荐）
    C. 屏幕可见但内容模糊
    """

    question: str
    element: str  # 引发问题的元素
    options: List[BoundaryOption]

    def to_dict(self) -> Dict:
        return {
            "question": self.question,
            "element": self.element,
            "options": [o.to_dict() for o in self.options],
        }


@dataclass
class ContextContaminationRisk:
    contaminant: str
    source_context: str
    active_context: str
    planned_evidence: str
    severity: str
    reason: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 动作/状态词库：用于识别可被暗示的元素和字面化风险
# ---------------------------------------------------------------------------

# 中文动作前缀："打X" / "看X" / "玩X" 等通常描述动作，
# 模型倾向于字面渲染动作的对象内容
ACTION_PREFIXES_ZH: Tuple[str, ...] = (
    "打", "看", "听", "玩", "吃", "喝", "做", "写", "画", "弹",
    "唱", "读", "拍", "追", "找", "用", "拿", "穿", "戴", "骑",
)

LITERALIZATION_ACTION_PREFIXES_ZH: Tuple[str, ...] = (
    "打", "看", "听", "玩", "读", "写", "画", "弹", "唱", "拍",
)

# 中文抽象/情感/状态词：这些难以直接渲染，通常需要暗示
ABSTRACT_CONCEPTS_ZH: Tuple[str, ...] = (
    "思考", "想念", "回忆", "梦到", "期待", "希望", "害怕",
    "开心", "伤心", "生气", "紧张", "放松", "享受", "沉浸",
    "孤独", "自由", "忙碌", "无聊", "犹豫", "决定",
)

# 中文具体实体词：这些通常是 must_show
CONCRETE_ENTITY_MARKERS_ZH: Tuple[str, ...] = (
    "小男孩", "小女孩", "男孩", "女孩", "男人", "女人", "小孩", "老人", "人",
    "手机", "电脑", "书", "车", "猫", "狗", "花", "树",
    "桌子", "椅子", "窗户", "门", "房子", "街道", "天空",
    "山", "海", "河", "湖", "草地", "森林", "城市",
    "教室", "办公室", "卧室", "厨房", "公园", "广场",
    "杯子", "瓶子", "包", "帽子", "眼镜", "耳机",
)

VISUAL_FORBIDDEN_MARKERS: Tuple[str, ...] = (
    "游戏UI", "游戏 UI", "UI", "界面", "文字", "字幕", "水印",
)

# 英文动作词
ACTION_VERBS_EN: Tuple[str, ...] = (
    "playing", "watching", "listening", "reading", "eating",
    "drinking", "writing", "drawing", "singing", "dancing",
    "running", "swimming", "cooking", "driving", "riding",
    "thinking", "dreaming", "hoping", "fearing",
)

# 常见字面化风险模式：(触发词, 字面渲染, 风险描述)
LITERALIZATION_PATTERNS_ZH: List[Tuple[str, str, str]] = [
    ("打游戏", "手机/电脑屏幕显示游戏 UI",
     "'打游戏'会被渲染为可见的游戏画面，焦点可能偏向屏幕而非人物"),
    ("玩游戏", "手机/电脑屏幕显示游戏 UI",
     "'玩游戏'会被渲染为可见的游戏画面，焦点可能偏向屏幕而非人物"),
    ("看书", "书页上显示清晰文字",
     "'看书'会被渲染为可见的书籍内容，可能产生不自然的文字"),
    ("读书", "书页上显示清晰文字",
     "'读书'会被渲染为可见的书籍内容，可能产生不自然的文字"),
    ("看手机", "手机屏幕显示具体内容",
     "'看手机'会被渲染为有内容的手机屏幕，可能产生乱码或不自然的 UI"),
    ("听音乐", "可见的耳机/音符/音响",
     "'听音乐'可能导致画面添加音符特效或过于强调耳机"),
    ("思考", "可见的思考泡泡或夸张表情",
     "'思考'可能被渲染为卡通思考泡泡或不自然的凝视"),
    ("想念", "可见的回忆画面或泡泡",
     "'想念'可能被渲染为画中画或思念对象的幽灵叠影"),
    ("伤心", "夸张的哭泣或泪水",
     "'伤心'可能导致过度渲染泪水，而非微妙的情感表达"),
    ("开心", "夸张的笑容",
     "'开心'可能导致过度渲染笑容，失去自然感"),
    ("写字", "纸上显示清晰文字",
     "'写字'会被渲染为可见的文字内容，AI 生成的文字通常不可读"),
    ("画画", "画布上显示具体画作",
     "'画画'会被渲染为可见的画作内容，可能产生画中画"),
    ("弹钢琴", "可见的钢琴和手指细节",
     "'弹钢琴'可能导致过度渲染手指，AI 生成的手指通常有问题"),
    ("拍照", "可见的相机取景框和照片内容",
     "'拍照'可能导致画中画效果"),
]


# ---------------------------------------------------------------------------
# 句子切分 + 关键词提取
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    parts = SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def _split_requirement_units(text: str) -> List[str]:
    units: List[str] = []
    for sent in _split_sentences(text):
        parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(sent)]
        parts = [p for p in parts if p]
        if len(parts) <= 1:
            units.append(sent)
        else:
            units.extend(parts)
    return units


def _extract_keywords(sentence: str) -> List[str]:
    """抽出可用作匹配的内容词。

    中文：在每段连续 CJK 字符上滑 2 / 3 字窗口，命中停用字单字符整体的丢弃。
    英文：长度 ≥ 3 且非停用词的小写单词。
    """
    keywords: List[str] = []

    for run in CJK_RE.findall(sentence):
        for n in (3, 2):
            if len(run) < n:
                continue
            for i in range(len(run) - n + 1):
                kw = run[i : i + n]
                # 整体在停用词里直接丢弃
                if kw in STOPWORDS:
                    continue
                keywords.append(kw)

    for w in EN_WORD_RE.findall(sentence):
        wl = w.lower()
        if wl in STOPWORDS:
            continue
        keywords.append(wl)

    # 去重保序
    seen = set()
    out: List[str] = []
    for k in keywords:
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def _detect_marker(sentence: str) -> Tuple[Optional[str], str]:
    """识别句子的 polarity；优先级：否定 > 正向 > 软。"""
    low = sentence.lower()
    for m in NEGATIVE_MARKERS_ZH:
        if m in sentence:
            return m, "must_not"
    for m in NEGATIVE_MARKERS_EN:
        if m in low:
            return m, "must_not"
    for m in POSITIVE_MARKERS_ZH:
        if m in sentence:
            return m, "must"
    for m in POSITIVE_MARKERS_EN:
        if m in low:
            return m.strip(), "must"
    return None, "soft"


# ---------------------------------------------------------------------------
# 要求抽取
# ---------------------------------------------------------------------------

def extract_requirements(context: str) -> List[Requirement]:
    """从用户上下文里抽出 Requirement 列表。

    规则：
    - 含正向 / 否定标记词的句子 → 高 strength。
    - 没有标记词但含 ≥ 2 个关键词的句子 → 软要求，初始 strength = 0.4。
    - 用户在多个软要求里反复出现的同一关键词 → 自动提权（说明用户在反复强调）。
    """
    requirements: List[Requirement] = []
    for sent in _split_requirement_units(context or ""):
        marker, polarity = _detect_marker(sent)
        keywords = _extract_keywords(sent)
        if not keywords:
            continue

        if polarity == "must":
            strength = 0.9
        elif polarity == "must_not":
            strength = 0.85
        else:
            # 软要求：句子要足够实质（≥ 2 个关键词）才保留
            if len(keywords) < 2:
                continue
            strength = 0.4

        requirements.append(
            Requirement(
                text=sent,
                polarity=polarity,
                keywords=keywords,
                strength=strength,
                marker=marker,
            )
        )

    _boost_repeated(requirements)
    return requirements


def _boost_repeated(reqs: List[Requirement]) -> None:
    """软要求里反复出现的关键词 → 用户在反复强调，提权。"""
    counts: Dict[str, int] = {}
    for r in reqs:
        for k in r.keywords:
            counts[k] = counts.get(k, 0) + 1
    for r in reqs:
        if r.polarity != "soft":
            continue
        if any(counts.get(k, 0) >= 3 for k in r.keywords):
            r.strength = min(0.85, r.strength + 0.3)


# ---------------------------------------------------------------------------
# 覆盖度计算
# ---------------------------------------------------------------------------

def _score_requirement(
    req: Requirement,
    output: str,
    output_low: str,
) -> RequirementCoverage:
    if not req.keywords:
        return RequirementCoverage(
            requirement=req,
            status="ignored",
            coverage=0.0,
            matched_keywords=[],
        )

    matched: List[str] = []
    for kw in req.keywords:
        if re.match(r"^[a-z0-9_-]+$", kw):
            if kw in output_low:
                matched.append(kw)
        else:
            if kw in output:
                matched.append(kw)

    coverage = len(matched) / len(req.keywords)

    if req.polarity == "must_not":
        # 否定要求门槛更低：n-gram 膨胀导致分母大，
        # 但只要核心概念出现在输出里就算违反。
        if coverage >= 0.3:
            status = "violated"
        elif coverage > 0.0:
            status = "weak"
        else:
            status = "reflected"
        return RequirementCoverage(
            requirement=req,
            status=status,
            coverage=round(coverage, 3),
            matched_keywords=matched,
            notes="否定要求：命中关键词意味着违反",
        )

    if coverage >= 0.6:
        status = "reflected"
    elif coverage >= 0.2:
        status = "weak"
    else:
        status = "ignored"
    return RequirementCoverage(
        requirement=req,
        status=status,
        coverage=round(coverage, 3),
        matched_keywords=matched,
    )


# ---------------------------------------------------------------------------
# 偏移度 + 下一轮纠偏
# ---------------------------------------------------------------------------

def _compute_drift(coverages: List[RequirementCoverage]) -> Tuple[str, float]:
    if not coverages:
        return "low", 0.0
    total = sum(c.requirement.strength for c in coverages) or 1.0
    bad = 0.0
    for c in coverages:
        if c.status == "ignored":
            bad += c.requirement.strength
        elif c.status == "violated":
            bad += c.requirement.strength * 1.2
        elif c.status == "weak":
            bad += c.requirement.strength * 0.4
    score = min(1.0, bad / total)
    if score >= 0.6:
        level = "high"
    elif score >= 0.3:
        level = "medium"
    else:
        level = "low"
    return level, round(score, 3)


def _next_turn_patch(coverages: List[RequirementCoverage]) -> List[str]:
    """生成下一轮纠偏提示。优先级：violated > ignored > weak。"""
    priority = {"violated": 0, "ignored": 1, "weak": 2, "reflected": 3}
    sorted_cov = sorted(
        coverages,
        key=lambda c: (priority.get(c.status, 9), -c.requirement.strength),
    )
    patches: List[str] = []
    for c in sorted_cov:
        if c.status == "violated":
            patches.append(f"下一轮务必避开：{c.requirement.text}")
        elif c.status == "ignored":
            patches.append(f"下一轮请把这个要求放回核心：{c.requirement.text}")
        elif c.status == "weak":
            patches.append(f"下一轮加强这个要求的回应：{c.requirement.text}")
        if len(patches) >= 5:
            break
    return patches


# ---------------------------------------------------------------------------
# 核心关注摘要
# ---------------------------------------------------------------------------

def _core_focus(output: str) -> List[str]:
    sentences = _split_sentences(output or "")
    if not sentences:
        return []
    focus: List[str] = [sentences[0][:80]]
    counts: Dict[str, int] = {}
    for s in sentences:
        for k in set(_extract_keywords(s)):
            counts[k] = counts.get(k, 0) + 1
    if counts:
        top_kw, top_n = max(counts.items(), key=lambda kv: kv[1])
        if top_n >= 2:
            focus.append(f"主要围绕「{top_kw}」展开")
    return focus


# ---------------------------------------------------------------------------
# Phase 7：注意力-输出控制 HUD 推导
#
# 下面这些函数 *只* 读已有的 requirements / coverages / agent_output，
# 把它们编排成 user_intent_map / agent_attention_map / attention_gaps /
# output_trajectory / control_levers。它们 *不* 引入新依赖、不调 LLM、
# 不读模型权重。
# ---------------------------------------------------------------------------

def _build_intent_map(reqs: List[Requirement]) -> List[IntentSignal]:
    """把 Requirement 列表转成归一化权重的用户意图地图。"""
    if not reqs:
        return []
    total = sum(r.strength for r in reqs) or 1.0
    out: List[IntentSignal] = []
    for r in reqs:
        if r.polarity == "must":
            priority = "must"
        elif r.polarity == "must_not":
            priority = "must_not"
        else:
            priority = "supporting"
        out.append(
            IntentSignal(
                label=r.text,
                priority=priority,
                weight=round(r.strength / total, 3),
                evidence=r.keywords[:3],
            )
        )
    return out


def _build_attention_map(
    agent_output: str,
    coverages: List[RequirementCoverage],
    top_n: int = 6,
    min_count: int = 2,
) -> List[AttentionSignal]:
    """从 agent 输出抽 top-N 高频关键词，标注它对齐到哪条 user 要求。

    - ``aligned``：命中 must 要求关键词，且要求被充分回应（reflected）。
    - ``partial``：命中 must 要求关键词，但要求只被弱化回应（weak/ignored）。
    - ``off_task``：未匹配任何 user 要求关键词。
    - ``violation``：命中 must_not 要求关键词。
    """
    sentences = _split_sentences(agent_output)
    if not sentences:
        return []

    counts: Dict[str, int] = {}
    sent_index: Dict[str, str] = {}
    for s in sentences:
        for k in set(_extract_keywords(s)):
            counts[k] = counts.get(k, 0) + 1
            if k not in sent_index:
                sent_index[k] = s

    items = [(k, n) for k, n in counts.items() if n >= min_count]
    if not items:
        # 退化：实在没人重复出现，就取出现过的 top-N 也比空列表好。
        items = list(counts.items())
    items.sort(key=lambda kv: -kv[1])
    items = items[:top_n]
    if not items:
        return []

    must_kws: Dict[str, RequirementCoverage] = {}
    must_not_kws: Dict[str, RequirementCoverage] = {}
    for c in coverages:
        for kw in c.requirement.keywords:
            if c.requirement.polarity == "must_not":
                must_not_kws.setdefault(kw, c)
            else:
                # 同一关键词可能落在多条要求上，优先记 reflected 的，
                # 这样 alignment 不会被 weak/ignored 拖低。
                existing = must_kws.get(kw)
                if existing is None or (
                    c.status == "reflected" and existing.status != "reflected"
                ):
                    must_kws[kw] = c

    total = sum(n for _, n in items) or 1
    out: List[AttentionSignal] = []
    for kw, n in items:
        weight = round(n / total, 3)
        ev_sentence = sent_index.get(kw, "")
        evidence = [ev_sentence[:80]] if ev_sentence else []
        if kw in must_not_kws:
            alignment = "violation"
        elif kw in must_kws:
            cov = must_kws[kw]
            alignment = "aligned" if cov.status == "reflected" else "partial"
        else:
            alignment = "off_task"
        out.append(
            AttentionSignal(
                label=kw,
                weight=weight,
                alignment=alignment,
                evidence=evidence,
            )
        )
    return out


def _build_attention_gaps(
    coverages: List[RequirementCoverage],
    attention_map: List[AttentionSignal],
) -> List[AttentionGap]:
    gaps: List[AttentionGap] = []
    for c in coverages:
        r = c.requirement
        if r.polarity == "must":
            if c.status == "ignored":
                gaps.append(
                    AttentionGap(
                        label=r.text,
                        kind="missing",
                        severity="high",
                        why="must 要求在 agent 输出里几乎未被回应",
                    )
                )
            elif c.status == "weak":
                gaps.append(
                    AttentionGap(
                        label=r.text,
                        kind="under_focused",
                        severity="medium",
                        why="must 要求被弱化，覆盖率不足",
                    )
                )
        elif r.polarity == "must_not" and c.status == "violated":
            gaps.append(
                AttentionGap(
                    label=r.text,
                    kind="over_focused",
                    severity="high",
                    why="agent 把注意力放到了被禁止的话题上",
                )
            )
    # off-task 高权重 attention：算 over_focused（对话偏题的主因之一）。
    for sig in attention_map:
        if sig.alignment == "off_task" and sig.weight >= 0.2:
            gaps.append(
                AttentionGap(
                    label=sig.label,
                    kind="over_focused",
                    severity="medium",
                    why="agent 注意力集中在用户要求之外的话题",
                )
            )
    return gaps


def _build_trajectory(
    requirements: List[Requirement],
    coverages: List[RequirementCoverage],
    attention_map: List[AttentionSignal],
    drift_level: str,
) -> OutputTrajectory:
    off_task = [s for s in attention_map if s.alignment == "off_task"]
    violations = [s for s in attention_map if s.alignment == "violation"]
    aligned = [s for s in attention_map if s.alignment == "aligned"]
    missed = [
        c for c in coverages
        if c.requirement.polarity == "must" and c.status == "ignored"
    ]

    why: List[str] = []
    if violations:
        why.append(f"输出在被禁止的话题上有较强注意力：{violations[0].label}")
    if off_task:
        why.append(f"输出大量注意力落在用户未要求的方向：{off_task[0].label}")
    if missed:
        why.append(
            f"必须项尚未进入 agent 输出焦点：{missed[0].requirement.text}"
        )
    if not why and aligned:
        why.append(f"输出注意力集中在用户要求上：{aligned[0].label}")

    if violations:
        likely = f"延续被禁止的方向：{violations[0].label}"
    elif off_task and (
        not aligned or off_task[0].weight > aligned[0].weight
    ):
        likely = f"延续偏离主题的方向：{off_task[0].label}"
    elif missed:
        likely = "继续展开当前已写内容，但仍漏掉用户的核心要求"
    elif aligned:
        likely = "继续按已表达的要求展开输出"
    else:
        likely = "暂无足够证据判断输出走向"

    if len(requirements) >= 2:
        confidence = "high"
    elif len(requirements) == 1:
        confidence = "medium"
    else:
        confidence = "low"

    return OutputTrajectory(
        likely_direction=likely,
        risk=drift_level,
        confidence=confidence,
        why=why,
    )


def _build_control_levers(
    coverages: List[RequirementCoverage],
    attention_map: List[AttentionSignal],
) -> ControlLevers:
    boost: List[str] = []
    suppress: List[str] = []
    stop_doing: List[str] = []
    return_to: List[str] = []

    seen_boost: set = set()
    seen_suppress: set = set()

    for c in coverages:
        r = c.requirement
        if r.polarity == "must" and c.status in {"ignored", "weak"}:
            if r.text not in seen_boost:
                boost.append(r.text)
                return_to.append(f"回到：{r.text}")
                seen_boost.add(r.text)
        elif r.polarity == "must_not" and c.status == "violated":
            if r.text not in seen_suppress:
                suppress.append(r.text)
                stop_doing.append(f"停止：{r.text}")
                seen_suppress.add(r.text)

    for sig in attention_map:
        if sig.alignment == "off_task" and sig.weight >= 0.2:
            if sig.label not in seen_suppress:
                suppress.append(sig.label)
                stop_doing.append(f"停止把注意力放到：{sig.label}")
                seen_suppress.add(sig.label)

    return ControlLevers(
        boost=boost,
        suppress=suppress,
        stop_doing=stop_doing,
        return_to=return_to,
    )


def _compute_interrupt(
    drift_level: str,
    coverages: List[RequirementCoverage],
) -> str:
    if drift_level == "high" or any(c.status == "violated" for c in coverages):
        return "interrupt"
    if drift_level == "medium":
        return "watch"
    return "ok"


def _preview_opening_patch(
    coverages: List[RequirementCoverage],
    levers: ControlLevers,
    risk_level: str,
) -> List[str]:
    patch: List[str] = []
    if risk_level == "high":
        patch.append("先不要进入正文；先重写 planned focus。")
    elif risk_level == "medium":
        patch.append("可以继续，但输出开头必须先拉回用户核心要求。")
    else:
        patch.append("可以继续；输出开头保持当前注意力分配。")

    for c in coverages:
        if c.requirement.polarity == "must" and c.status in {
            "ignored",
            "weak",
        }:
            patch.append(f"开头先覆盖：{c.requirement.text}")
        elif c.requirement.polarity == "must_not" and c.status in {
            "violated",
            "weak",
        }:
            patch.append(f"开头明确不要展开：{c.requirement.text}")
        if len(patch) >= 5:
            break

    for item in levers.return_to:
        if len(patch) >= 5:
            break
        patch.append(item)
    return patch


def _build_activation_decision(
    should_continue: bool,
    risk_level: str,
    gaps: List[AttentionGap],
    patch: List[str],
    boundary_questions: List["BoundaryQuestion"],
    contamination_risks: List["ContextContaminationRisk"],
) -> ActivationDecision:
    if any(r.severity == "high" for r in contamination_risks):
        return ActivationDecision(
            action="cut_context_contamination",
            should_stop=True,
            reason="planned_focus is following older context instead of the latest pivot",
            message="先切断旧上下文污染，再重写 planned_focus。",
            blockers=["context_contamination"],
            next_steps=patch,
        )

    if not should_continue:
        blockers = ["high_preview_risk"] if risk_level == "high" else []
        blockers.extend(g.kind for g in gaps if g.severity == "high")
        return ActivationDecision(
            action="rewrite_planned_focus",
            should_stop=True,
            reason="planned_focus misses or violates high-priority user requirements",
            message="不要进入正文；先按 opening_patch 重写 planned_focus。",
            blockers=blockers or ["misaligned_planned_focus"],
            next_steps=patch,
        )

    if boundary_questions:
        question = boundary_questions[0]
        return ActivationDecision(
            action="ask_boundary_question",
            should_stop=True,
            reason="creative prompt has an ambiguous visual boundary",
            message=question.question,
            blockers=["boundary_question"],
            next_steps=[
                f"Ask: {question.question}",
                "Merge the user's A/B/C answer into context.",
                "Run preview again if the visual boundary changed.",
            ],
        )

    return ActivationDecision(
        action="continue",
        should_stop=False,
        reason="planned_focus is aligned enough to start",
        message="可以继续；输出开头保持当前注意力分配。",
        blockers=[],
        next_steps=patch,
    )


# ---------------------------------------------------------------------------
# 边界分解：must_show / can_imply / must_not_show
# ---------------------------------------------------------------------------

def _classify_element(keyword: str, source_text: str, polarity: str) -> BoundaryItem:
    """把一个关键词分类为 must_show / can_imply / must_not_show。

    规则：
    - must_not 极性要求的关键词 → must_not_show
    - 匹配具体实体词库 → must_show
    - 匹配动作前缀或抽象概念词库 → can_imply
    - 其余默认 must_show（宁可多显示不可漏）
    """
    if polarity == "must_not":
        return BoundaryItem(
            element=keyword,
            category="must_not_show",
            reason="用户明确禁止",
            source_text=source_text,
        )

    # 检查是否是抽象/情感/状态概念
    for concept in ABSTRACT_CONCEPTS_ZH:
        if concept in keyword or keyword in concept:
            return BoundaryItem(
                element=keyword,
                category="can_imply",
                reason="抽象/情感概念，可通过暗示表达",
                source_text=source_text,
            )

    # 检查是否是动作短语（"打X" / "看X" 等）
    for prefix in ACTION_PREFIXES_ZH:
        if keyword.startswith(prefix) and len(keyword) >= 2:
            return BoundaryItem(
                element=keyword,
                category="can_imply",
                reason=f"动作短语（{prefix}+…），可通过姿态/构图暗示",
                source_text=source_text,
            )

    # 英文动作词
    kw_low = keyword.lower()
    for verb in ACTION_VERBS_EN:
        if verb in kw_low:
            return BoundaryItem(
                element=keyword,
                category="can_imply",
                reason="action verb, can be implied through composition",
                source_text=source_text,
            )

    # 具体实体
    for entity in CONCRETE_ENTITY_MARKERS_ZH:
        if entity in keyword or keyword in entity:
            return BoundaryItem(
                element=keyword,
                category="must_show",
                reason="具体实体/物件",
                source_text=source_text,
            )

    # 默认：must_show
    return BoundaryItem(
        element=keyword,
        category="must_show",
        reason="用户提到的元素，默认应呈现",
        source_text=source_text,
    )


def _extract_boundary_candidates(sentence: str, polarity: str) -> List[str]:
    """抽取适合展示给用户的视觉边界候选。

    这里刻意不复用 `_extract_keywords` 的中文 n-gram；n-gram 适合覆盖度
    匹配，但不适合直接展示给用户。边界候选只保留稳定可读的实体、动作
    风险触发词和抽象状态词。
    """
    candidates: List[str] = []

    for trigger, _, _ in LITERALIZATION_PATTERNS_ZH:
        if trigger in sentence:
            candidates.append(trigger)

    for entity in CONCRETE_ENTITY_MARKERS_ZH:
        if entity in sentence:
            candidates.append(entity)

    for concept in ABSTRACT_CONCEPTS_ZH:
        if concept not in sentence:
            continue
        if f"{concept}感" in sentence:
            candidates.append(f"{concept}感")
        else:
            candidates.append(concept)

    if polarity == "must_not":
        for marker in VISUAL_FORBIDDEN_MARKERS:
            if marker in sentence:
                candidates.append(marker.replace(" ", ""))

    low = sentence.lower()
    for verb in ACTION_VERBS_EN:
        if verb in low:
            candidates.append(verb)

    if polarity == "must_not" and not candidates:
        # 回退：从 n-gram 关键词里挑「不带功能字打头」且尽量长的几个，
        # 避免渲染出 `不要把 / 要把格 / 把格式` 这类碎片。
        # 这些字在中文里多半是助词 / 否定词 / 副词，不是用户真正想表达的对象。
        skip_leading = ("不", "别", "勿", "要", "把", "让", "使", "给", "为",
                        "在", "就", "都", "没", "也", "还", "再", "又",
                        "当", "成", "做", "搞")
        ngrams = _extract_keywords(sentence)
        # 优先 3-gram，再补 2-gram；都跳过坏开头
        cleaned = [
            kw for kw in ngrams
            if len(kw) >= 3 and not kw.startswith(skip_leading)
        ]
        if not cleaned:
            cleaned = [
                kw for kw in ngrams
                if len(kw) >= 2 and not kw.startswith(skip_leading)
            ]
        if not cleaned:
            # 实在没有就退回原 n-gram 前 1 个，保底（极少触发）
            cleaned = ngrams[:1]
        # 只取最干净的一个，避免滑窗 n-gram 把同一概念渲染三遍
        # （如 `格式化 / 式化当 / 化当主`）。要表达多个 must_not
        # 概念时，用户通常会分子句写，由 _split_requirement_units 兜住。
        candidates.extend(cleaned[:1])

    seen: set = set()
    out: List[str] = []
    for item in candidates:
        if item in seen:
            continue
        if any(item in existing and item != existing for existing in out):
            continue
        out = [
            existing for existing in out
            if not (existing in item and existing != item)
        ]
        seen.add(item)
        out.append(item)
    return out


def _decompose_boundaries(
    requirements: List[Requirement],
    user_context: str,
) -> BoundaryDecomposition:
    """从要求列表中分解出 must_show / can_imply / must_not_show 边界。"""
    must_show: List[BoundaryItem] = []
    can_imply: List[BoundaryItem] = []
    must_not_show: List[BoundaryItem] = []

    seen: set = set()
    for req in requirements:
        for kw in _extract_boundary_candidates(req.text, req.polarity):
            if kw in seen:
                continue
            seen.add(kw)
            item = _classify_element(kw, req.text, req.polarity)
            if item.category == "must_show":
                must_show.append(item)
            elif item.category == "can_imply":
                can_imply.append(item)
            else:
                must_not_show.append(item)

    # 对无要求但 user_context 有内容的情况，做整句扫描
    if not requirements and user_context.strip():
        for sent in _split_sentences(user_context):
            for kw in _extract_boundary_candidates(sent, "soft"):
                if kw in seen:
                    continue
                seen.add(kw)
                item = _classify_element(kw, sent, "soft")
                if item.category == "must_show":
                    must_show.append(item)
                elif item.category == "can_imply":
                    can_imply.append(item)

    return BoundaryDecomposition(
        must_show=must_show,
        can_imply=can_imply,
        must_not_show=must_not_show,
    )


# ---------------------------------------------------------------------------
# 字面化风险检测
# ---------------------------------------------------------------------------

def _detect_literalization(user_context: str) -> List[LiteralizationRisk]:
    """扫描用户上下文，识别会被模型字面渲染的动作/状态。"""
    risks: List[LiteralizationRisk] = []
    seen: set = set()

    # 模式匹配：已知的高频字面化风险
    for trigger, literal, desc in LITERALIZATION_PATTERNS_ZH:
        if trigger in user_context and trigger not in seen:
            seen.add(trigger)
            risks.append(LiteralizationRisk(
                element=trigger,
                literal_interpretation=literal,
                risk_description=desc,
                severity="high",
            ))

    # 通用动作前缀扫描：捕获模式表以外的动作短语
    for sent in _split_sentences(user_context):
        for prefix in LITERALIZATION_ACTION_PREFIXES_ZH:
            idx = sent.find(prefix)
            if idx == -1:
                continue
            # 提取 "打X" / "看X" 短语（取后续 1-3 个字）
            rest = sent[idx + len(prefix):]
            cjk_after = CJK_RE.match(rest)
            if cjk_after:
                phrase = prefix + cjk_after.group()[:3]
                if phrase in seen or len(phrase) <= 1:
                    continue
                # 检查是否已经被模式表覆盖
                if any(phrase == t for t, _, _ in LITERALIZATION_PATTERNS_ZH):
                    continue
                seen.add(phrase)
                risks.append(LiteralizationRisk(
                    element=phrase,
                    literal_interpretation=f"'{phrase}'的对象内容会被字面渲染到画面中",
                    risk_description=f"动作'{prefix}…'倾向于让模型渲染动作对象的具体内容",
                    severity="medium",
                ))

    # 抽象概念扫描
    for concept in ABSTRACT_CONCEPTS_ZH:
        element = f"{concept}感" if f"{concept}感" in user_context else concept
        if concept in user_context and element not in seen:
            seen.add(element)
            risks.append(LiteralizationRisk(
                element=element,
                literal_interpretation=f"'{element}'可能被渲染为夸张的视觉表现",
                risk_description=f"抽象概念'{element}'难以自然地视觉化，模型倾向于字面/卡通化处理",
                severity="medium",
            ))

    return risks


# ---------------------------------------------------------------------------
# 边界反问生成
# ---------------------------------------------------------------------------

def _generate_boundary_questions(
    literalization_risks: List[LiteralizationRisk],
    boundary: BoundaryDecomposition,
) -> List[BoundaryQuestion]:
    """为每个有字面化风险的元素生成选项式边界反问。"""
    questions: List[BoundaryQuestion] = []

    for risk in literalization_risks:
        if risk.severity not in ("high", "medium"):
            continue

        # 生成针对该元素的选项
        options = _make_options_for_risk(risk)
        question = f"你是否真的想看到{risk.element}的画面？"
        if any(c in risk.element for c in ABSTRACT_CONCEPTS_ZH):
            question = f"'{risk.element}'需要直接符号化，还是自然暗示？"
        questions.append(BoundaryQuestion(
            question=question,
            element=risk.element,
            options=options,
        ))

        if len(questions) >= 5:
            break

    # 对 can_imply 中没有字面化风险的元素也生成轻量反问
    risk_elements = {r.element for r in literalization_risks}
    for item in boundary.can_imply:
        if any(
            item.element == risk_element
            or item.element in risk_element
            or risk_element in item.element
            for risk_element in risk_elements
        ):
            continue
        if len(questions) >= 5:
            break
        questions.append(BoundaryQuestion(
            question=f"'{item.element}'需要直接呈现还是暗示？",
            element=item.element,
            options=[
                BoundaryOption(
                    label="A",
                    description=f"直接呈现'{item.element}'的具体内容",
                ),
                BoundaryOption(
                    label="B",
                    description=f"通过构图/姿态暗示'{item.element}'",
                    recommended=True,
                ),
            ],
        ))

    return questions


def _make_options_for_risk(risk: LiteralizationRisk) -> List[BoundaryOption]:
    """为一个字面化风险生成 A/B/C 选项。"""
    element = risk.element
    literal = risk.literal_interpretation

    if any(c in element for c in ABSTRACT_CONCEPTS_ZH):
        return [
            BoundaryOption(
                label="A",
                description=f"直接强化'{element}'，允许明显表情/符号/特效",
            ),
            BoundaryOption(
                label="B",
                description=f"保持自然，通过表情、姿态和构图暗示'{element}'",
                recommended=True,
            ),
            BoundaryOption(
                label="C",
                description=f"只保留轻微'{element}'，不要添加符号化元素",
            ),
        ]

    return [
        BoundaryOption(
            label="A",
            description=f"是，画面中要有{literal}",
        ),
        BoundaryOption(
            label="B",
            description=f"不，通过姿态/构图暗示'{element}'就行",
            recommended=True,
        ),
        BoundaryOption(
            label="C",
            description=f"部分呈现：{literal.split('/')[0]}可见但内容模糊",
        ),
    ]


PIVOT_MARKERS_ZH: Tuple[str, ...] = (
    "现在", "当前", "这次", "接下来", "改成", "换成",
    "重点是", "核心是", "不是", "而是", "不要", "别再",
)

PIVOT_MARKERS_EN: Tuple[str, ...] = (
    "now", "current", "this time", "instead", "switch to",
    "focus on", "not", "rather than", "do not", "don't",
)


def _extract_contamination_terms(text: str) -> List[str]:
    terms: List[str] = []
    low = (text or "").lower()

    for word in EN_WORD_RE.findall(text or ""):
        term = word.lower()
        if term not in STOPWORDS:
            terms.append(term)

    for marker in CONCRETE_ENTITY_MARKERS_ZH:
        if marker in text:
            terms.append(marker)
    for marker in ABSTRACT_CONCEPTS_ZH:
        if marker in text:
            terms.append(marker)
    for trigger, _, _ in LITERALIZATION_PATTERNS_ZH:
        if trigger in text:
            terms.append(trigger)

    seen = set()
    out: List[str] = []
    for term in terms:
        normalized = term.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _find_active_context_index(sentences: List[str]) -> int:
    if not sentences:
        return 0
    for idx in range(len(sentences) - 1, -1, -1):
        sent = sentences[idx]
        low = sent.lower()
        if any(marker in sent for marker in PIVOT_MARKERS_ZH):
            return idx
        if any(marker in low for marker in PIVOT_MARKERS_EN):
            return idx
    return len(sentences) - 1


def _detect_context_contamination(
    user_context: str,
    planned_focus: str,
) -> List[ContextContaminationRisk]:
    sentences = _split_sentences(user_context)
    if len(sentences) < 2:
        return []

    active_idx = _find_active_context_index(sentences)
    previous = sentences[:active_idx]
    if not previous:
        return []

    active_context = "。".join(sentences[active_idx:])
    active_terms = set(_extract_contamination_terms(active_context))
    planned_terms = set(_extract_contamination_terms(planned_focus))
    if not planned_terms:
        return []

    active_overlap = planned_terms & active_terms
    risks: List[ContextContaminationRisk] = []
    for sent in previous:
        previous_terms = set(_extract_contamination_terms(sent))
        overlap = sorted((previous_terms & planned_terms) - active_terms)
        if not overlap:
            continue
        severity = "high" if active_terms and not active_overlap else "medium"
        risks.append(ContextContaminationRisk(
            contaminant=", ".join(overlap[:5]),
            source_context=sent,
            active_context=active_context,
            planned_evidence=planned_focus,
            severity=severity,
            reason=(
                "planned_focus 命中了较早上下文，但没有覆盖当前转向后的核心要求"
                if severity == "high"
                else "planned_focus 同时命中了旧上下文和当前上下文，需确认旧任务不是残留污染"
            ),
        ))

    return risks[:3]


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def preview_attention(
    user_context: str,
    planned_focus: str,
) -> AttentionPreview:
    user_context = user_context or ""
    planned_focus = planned_focus or ""

    requirements = extract_requirements(user_context)
    planned_low = planned_focus.lower()
    coverages = [
        _score_requirement(r, planned_focus, planned_low) for r in requirements
    ]

    risk_level, risk_score = _compute_drift(coverages)
    intent_map = _build_intent_map(requirements)
    planned_map = _build_attention_map(planned_focus, coverages)
    gaps = _build_attention_gaps(coverages, planned_map)
    levers = _build_control_levers(coverages, planned_map)

    # 边界分解 + 字面化检测 + 反问生成
    boundary = _decompose_boundaries(requirements, user_context)
    literalization_risks = _detect_literalization(user_context)
    boundary_questions = _generate_boundary_questions(
        literalization_risks, boundary
    )
    contamination_risks = _detect_context_contamination(
        user_context, planned_focus
    )

    # 字面化风险参与 risk_level 计算：高风险至少 medium，多个高风险 high
    high_lit = sum(1 for r in literalization_risks if r.severity == "high")
    if high_lit >= 2 and risk_level == "low":
        risk_level = "medium"
        risk_score = max(risk_score, 0.45)
    elif high_lit >= 1 and risk_level == "low":
        risk_level = "medium"
        risk_score = max(risk_score, 0.35)

    high_contamination = any(
        r.severity == "high" for r in contamination_risks
    )
    if high_contamination:
        risk_level = "high"
        risk_score = max(risk_score, 0.75)
    elif contamination_risks and risk_level == "low":
        risk_level = "medium"
        risk_score = max(risk_score, 0.50)

    should_continue = risk_level != "high" and not any(
        c.status == "violated" for c in coverages
    )
    patch = _preview_opening_patch(coverages, levers, risk_level)

    for risk in contamination_risks[:2]:
        if len(patch) >= 5:
            break
        patch.append(
            f"切断旧上下文污染：不要继续 {risk.contaminant}，回到当前任务"
        )

    # 把字面化风险也补进 patch（提醒用户在正文前确认边界）
    for risk in literalization_risks[:2]:
        if len(patch) >= 5:
            break
        patch.append(
            f"先确认：{risk.element} 是否要按字面渲染（{risk.literal_interpretation}）"
        )

    notes: List[str] = [
        "本预览显示的是输出前的 planned attention，不是模型内部神经注意力。",
        "它用于在正文开始前暴露注意力分配，让用户及时止损。",
    ]
    if not requirements:
        notes.append("未识别到明确要求；建议补充用户上下文。")
    if literalization_risks:
        notes.append(
            f"检测到 {len(literalization_risks)} 个字面化风险；"
            f"建议先回答 boundary_questions 再生成。"
        )
    if contamination_risks:
        notes.append(
            f"检测到 {len(contamination_risks)} 个上下文污染风险；"
            f"建议先切断旧任务残留再继续。"
        )

    activation_decision = _build_activation_decision(
        should_continue=should_continue,
        risk_level=risk_level,
        gaps=gaps,
        patch=patch,
        boundary_questions=boundary_questions,
        contamination_risks=contamination_risks,
    )

    return AttentionPreview(
        user_intent_map=intent_map,
        planned_attention_map=planned_map,
        missing_before_start=gaps,
        risk_level=risk_level,
        risk_score=risk_score,
        should_continue=should_continue,
        opening_patch=patch,
        control_levers=levers,
        activation_decision=activation_decision,
        boundary_decomposition=boundary,
        literalization_risks=literalization_risks,
        boundary_questions=boundary_questions,
        context_contamination_risks=contamination_risks,
        notes=notes,
    )


def analyze_attention(
    user_context: str,
    agent_output: str,
) -> AttentionHUD:
    """生成注意力仪表盘。

    这是 StateProbe Skill 的对外主函数。它不依赖 API、不依赖 GPU。
    Phase 7 起返回完整的 attention-to-output 控制 HUD。
    """
    user_context = user_context or ""
    agent_output = agent_output or ""

    requirements = extract_requirements(user_context)
    output_low = agent_output.lower()

    coverages = [
        _score_requirement(r, agent_output, output_low) for r in requirements
    ]

    reflected = [
        c for c in coverages
        if c.status == "reflected" and c.requirement.polarity != "must_not"
    ]
    # 否定要求里「成功避开」也算 reflected，但单独标识更易读。
    avoided = [
        c for c in coverages
        if c.status == "reflected" and c.requirement.polarity == "must_not"
    ]
    reflected = reflected + avoided
    weak = [c for c in coverages if c.status == "weak"]
    ignored = [c for c in coverages if c.status == "ignored"]
    violated = [c for c in coverages if c.status == "violated"]

    drift_level, drift_score = _compute_drift(coverages)
    patches = _next_turn_patch(coverages)
    focus = _core_focus(agent_output)

    intent_map = _build_intent_map(requirements)
    attention_map = _build_attention_map(agent_output, coverages)
    gaps = _build_attention_gaps(coverages, attention_map)
    trajectory = _build_trajectory(
        requirements, coverages, attention_map, drift_level
    )
    levers = _build_control_levers(coverages, attention_map)
    interrupt_level = _compute_interrupt(drift_level, coverages)

    notes: List[str] = [
        "本仪表盘显示的是任务注意力（用户要求 vs 输出回应）。",
        "它不是模型的真实神经注意力；后者由未来的企业 Runtime Probe 提供。",
        "output_trajectory 是基于词频与覆盖度的启发式预测，不是模型未来 token 的真实预测。",
    ]
    if not requirements:
        notes.append("未识别到明确要求；建议补充用户上下文以提升仪表盘信噪比。")

    return AttentionHUD(
        core_focus=focus,
        reflected=reflected,
        weak=weak,
        ignored=ignored,
        violated=violated,
        drift_level=drift_level,
        drift_score=drift_score,
        next_turn_patch=patches,
        notes=notes,
        user_intent_map=intent_map,
        agent_attention_map=attention_map,
        attention_gaps=gaps,
        output_trajectory=trajectory,
        control_levers=levers,
        interrupt_level=interrupt_level,
    )

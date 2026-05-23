# StateProbe Development Guide

面向贡献者和你自己 6 个月后的开发文档。讲项目结构、开发流程、加新能力的具体路径、测试策略、发版流程。**不讲产品定位**（那在 README 和战略蓝图里）。

---

## 1. 架构概览

按 [ADR_009](adr/009-hybrid-engine.md) 落地的四层架构：

```
prompt
  │
  ▼
┌─ Layer 1: Structural detector ──────────────────┐  always-on
│  长度 / 重复 / 同义词堆叠（不归任何轴）           │
│  → List[StructuralWarning]                       │
└──────────────────────────────────────────────────┘
  │
  ▼
┌─ Layer 2: Evidence contributors ─────────────────┐
│  ┌── StaticRuleContributor ─────────────────────┐│  always-on
│  │  正则规则匹配 → AxisEvidence[]                 ││
│  └───────────────────────────────────────────────┘│
│  ┌── LLMJudgeContributor (可选) ────────────────┐│  --llm-augment 开启
│  │  judge LLM 输出每轴 direction+confidence       ││
│  │  → AxisEvidence[]                              ││
│  └───────────────────────────────────────────────┘│
│  (未来: EmbeddingContributor / LabContributor)    │
│                                                    │
│  合并池: Dict[Axis, List[AxisEvidence]]           │
└──────────────────────────────────────────────────┘
  │
  ▼
┌─ Layer 3: Aggregator (纯函数) ──────────────────┐
│  按 confidence 阈值过滤                          │
│  per-axis: tanh(Σ strength × direction × conf)   │
│  + baseline = AxisReading.value                  │
└──────────────────────────────────────────────────┘
  │
  ▼
┌─ Layer 4: Reasoner (纯函数) ────────────────────┐
│  readings + target → deltas                      │
│  deltas → suggestions（按 abs_delta 排序 top-N）  │
│  readings + baseline → overlaps                  │
└──────────────────────────────────────────────────┘
```

四个不变量：
1. **Sensor 哑**：只发 evidence，不算 reading
2. **Aggregator 唯一**：所有 contributor 共享同一个聚合公式
3. **Evidence 类型统一**：聚合层不知道证据来自谁
4. **可选层失败 = 静默**：不打断流程，不通知用户

---

## 2. 项目结构

```
stateprobe/
├── stateprobe/                 # 主包
│   ├── __init__.py             # 导出公共 API: diagnose / Engine / Contributor
│   ├── models.py               # 核心 dataclass: Axis / AxisEvidence / AxisReading / Report
│   ├── rules.py                # 静态规则库（30+ 条正则规则）
│   ├── structural.py           # 结构警告（长度/重复/同义词）
│   ├── detector.py             # 编排: detect_readings / diagnose
│   ├── rewriter.py             # 改写建议生成
│   ├── html_report.py          # HTML 报告渲染
│   ├── cli.py                  # CLI（click + rich）
│   ├── engines/                # Evidence Contributors
│   │   ├── __init__.py
│   │   ├── base.py             # EvidenceContributor Protocol + 异常
│   │   ├── static.py           # StaticRuleContributor
│   │   └── llm_judge.py        # LLMJudgeContributor（OpenAI 兼容 API）
│   ├── eval/                   # Black-box 输出评测（v0.1+）
│   └── lab/                    # 开源模型激活探针（v0.4，实验）
│
├── tests/                      # pytest 单元 + 集成测试
├── scripts/                    # 验收脚本 / benchmark / 工具
│   ├── acceptance_check.py     # 工程标准验收（必须通过）
│   ├── acceptance_v02_stress.py # 真实用户压力测试
│   └── ...
├── benchmarks/                 # DeepSeek 行为校准 case
├── demos/                      # 可直接跑的 prompt 示例
├── docs/                       # 项目文档
│   ├── ARCHITECTURE.md         # 架构总图（这份是简版）
│   ├── DEVELOPMENT.md          # 本文档
│   ├── adr/                    # 架构决策 ADR
│   ├── governance/             # 项目治理 / 内部規划 / RUNBOOK
│   ├── archive/                # 历史版本报告（v0.2 / v0.3）
│   └── ...
├── pyproject.toml              # 包定义 + 依赖
└── README.md                   # 用户入口
```

---

## 3. 开发环境

### 3.1 系统要求

- Python ≥ 3.9（推荐 3.11 / 3.12）
- Windows / macOS / Linux 都可
- 可选：CUDA GPU（仅 lab 模块需要）

### 3.2 一次性 setup

```powershell
# 克隆
git clone ssh://git@ssh.github.com:443/Erye932/stateprobe.git
cd stateprobe

# 装为可编辑包（dev 依赖）
pip install -e ".[dev]"

# 校验：
python -m pytest -q
python scripts/acceptance_check.py
```

如果上面两条都过，环境就 OK。

### 3.3 LLM 引擎 setup（可选）

```powershell
# Windows PowerShell
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxx"

# 或写到 .env（不进 git）
echo "DEEPSEEK_API_KEY=sk-xxxxxxxx" > .env
```

测试 LLM 引擎：

```powershell
python -m stateprobe.cli check --llm-augment "请客观但多看积极面"
```

### 3.4 lab 模块 setup（v0.4 起需要）

```powershell
pip install -e ".[lab]"
# torch / transformers / accelerate / safetensors 一并装上
```

---

## 4. 日常开发循环

### 4.1 改一个 bug 的标准流程

1. 找到根因（不是症状）
2. **先写一个 regression test 让它 fail**
3. 修代码
4. 测试转 pass
5. 跑全套：`python -m pytest -q && python scripts/acceptance_check.py`
6. commit：`fix(<module>): <one line>`

### 4.2 加一个新功能

1. 在 [`docs/adr/decisions.md`](adr/decisions.md) 写一条决定（即使简短）
2. 大改动 → 在 `docs/adr/NNN-xxx.md` 写 ADR 等审核
3. 写测试（先 fail）
4. 实现
5. 跑测试 + acceptance + 压力测
6. 更新 CHANGELOG
7. 更新 README（如果是用户可见特性）

### 4.3 commit 规范

格式：`<type>(<scope>): <subject>`

types: `feat | fix | docs | test | refactor | chore | perf`

举例：
```
feat(engines): add LLMJudgeContributor with confidence gating
fix(detector): is_trivial false-positive when LLM emits empty sources
docs(adr): record hybrid engine decision
test(contributors): regression for synthetic source bug
refactor(rewriter): extract suggestion top-N truncation
```

---

## 5. 加新能力的具体路径

### 5.1 加一个新的静态规则

例：抓「请帮我」这种过度礼貌迎合。

1. 打开 `stateprobe/rules.py`
2. 在合适的 axis section（如 `_SYCOPHANCY_RULES`）加一条：

```python
Rule(
    id="sycophancy.help_me_please",
    axis=Axis.SYCOPHANCY,
    direction=+1,
    pattern=re.compile(r"请帮我|麻烦你"),
    weight=0.20,
    explanation_zh="过度礼貌请求容易触发模型的迎合表现",
    citation="ELEPHANT 2025",
),
```

3. 在 `tests/test_rules.py` 加测试

```python
def test_help_me_polite_caught():
    sources = run_static_rules("请帮我看看这个项目")
    assert any(s.rule_id == "sycophancy.help_me_please" for s in sources)
```

4. `python -m pytest tests/test_rules.py -v`

### 5.2 加一个新的轴

例：加 `confidence_calibration`（自信度校准——「我可能错」的量）。

1. `stateprobe/models.py`：在 `Axis` enum 加：

```python
class Axis(Enum):
    SYCOPHANCY = ("sycophancy", "迎合度", "敢说不行", "全盘点赞")
    ...
    CONFIDENCE_CALIBRATION = (
        "confidence_calibration",
        "自信度校准",
        "敢断言",
        "满嘴可能",
    )
```

2. 给所有 `TARGET_PRESETS` 加这个轴的目标值（5 个 preset 一个不能漏）
3. 给所有 `MODEL_BASELINES` 加这个轴的基线（v3-pro / v3-flash / v4-pro / v4-flash / deepseek / generic）
4. 至少加 2 条静态规则覆盖这个轴
5. 跑测试：`python -m pytest tests/test_rules.py::test_every_axis_has_at_least_two_rules`

### 5.3 加一个新的 EvidenceContributor

例：加 EmbeddingContributor（v0.3 嵌入兜底）。

1. 在 `stateprobe/engines/` 新建 `embedding.py`
2. 实现 Protocol：

```python
from .base import EvidenceContributor
from ..models import Axis, AxisEvidence

class EmbeddingContributor:
    name = "embedding"

    def __init__(self, model_path: str = "bge-small-zh"):
        # lazy load
        self._model = None
        self._model_path = model_path

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[AxisEvidence]]:
        if self._model is None:
            self._lazy_load()
        # ... compute embeddings, project to axis directions, gate by confidence
        return {axis: [...] for axis in Axis}

    def _lazy_load(self):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self._model_path)
```

3. 在 `stateprobe/engines/__init__.py` 导出
4. CLI 加 `--embedding-augment` 开关（参考 `--llm-augment`）
5. 写测试：`tests/test_embedding_contributor.py`，至少包括：
   - 正常 prompt 返回 sources
   - 模型不可用时抛 EngineUnavailable
   - confidence 低于阈值的不进入结果

### 5.4 加一个新的目标预设

`stateprobe/models.py` 的 `TARGET_PRESETS`：

```python
"creative_brainstorm": Target(
    name="creative_brainstorm",
    label_zh="创意发散",
    description_zh="头脑风暴/创意拓展场景，鼓励发散，反迎合次要",
    coordinates={
        Axis.SYCOPHANCY: 0.50,
        Axis.TASK_WIDTH: 0.85,
        Axis.ACCEPTANCE_CLARITY: 0.30,
        Axis.REASONING_BUDGET: 0.40,
        Axis.IDENTITY_STRENGTH: 0.30,
        Axis.CONFIDENCE: 0.50,
        Axis.SELF_VERIFICATION: 0.30,
        Axis.INFO_FLOW: 0.50,
    },
),
```

测试 `test_rules.py::test_target_preset_coordinates_in_range` 自动覆盖。

---

## 6. 测试策略

### 6.1 测试金字塔

| 层级 | 数量 | 速度 | 工具 |
|---|---|---|---|
| 单元测试 | 80+ | < 1s/全部 | pytest |
| 集成测试（hybrid） | 5-10 | < 3s/全部 | pytest + fake LLM |
| 验收测试（acceptance_check） | 25+ | < 5s/全部 | scripts/acceptance_check.py |
| 真实压力测试 | 15 用例 | ~ 60s（含 LLM 调用） | scripts/acceptance_v02_stress.py |

### 6.2 命令清单

```powershell
# 跑全部单元测试（最快）
python -m pytest -q

# 跑特定文件
python -m pytest tests/test_detector.py -v

# 跑特定测试
python -m pytest tests/test_detector.py::test_diagnose_default_uses_static -v

# 带覆盖率
python -m pytest --cov=stateprobe --cov-report=html
# 然后看 htmlcov/index.html

# 工程标准验收（必须 100% pass 才能 release）
python scripts/acceptance_check.py

# 真实 LLM 压力测试（消耗 API 配额，一次约 14 次调用）
python scripts/acceptance_v02_stress.py
# 输出到 docs/archive/v0.2/stress_report.txt
```

### 6.3 写测试的原则

1. **每个 bug 必须先写 regression test**（让它 fail），再修
2. **用 fake / mock LLM**，不要在 unit test 里打真 API
3. **测试名 = 行为描述**：`test_<subject>_<expected_behavior>_<condition>`
4. **不要测实现细节**，测可观察行为（输入 → 输出）
5. **trivial 检测、confidence 阈值、suggestions top-N 这些边界**必须有测试

---

## 7. 编码规范

### 7.1 Python 风格

- PEP 8，4 空格缩进
- 类型注解（必须，公共 API 强制）
- `from __future__ import annotations` 支持 3.9
- f-string 优先于 `%` 或 `.format()`
- dataclass 优先于裸 class
- 不用 `print` 调试（用 `logging` 或测试）

### 7.2 文档字符串

公共 API 必须有 docstring。格式（Google 风格）：

```python
def diagnose(
    prompt: str,
    target_name: str = "calm_reasoning",
    *,
    llm_augment: Optional[LLMJudgeContributor] = None,
) -> Report:
    """诊断一段 prompt 的行为压力。

    Args:
        prompt: 用户提示词
        target_name: 目标预设名（calm_reasoning / direct_answer ...）
        llm_augment: 可选 LLM 判断器，传入则启用语义层证据

    Returns:
        Report 包含读数、deltas、建议、警告等

    Raises:
        ValueError: target_name 不在已知预设里
    """
```

### 7.3 注释

- 解释「为什么」，不解释「做什么」（代码自解释）
- 复杂算法旁边引用论文 / ADR
- TODO 必须带 owner 和 issue 链接：`# TODO(@yourname, #42): xxx`

---

## 8. 发版流程

### 8.1 版本号策略（SemVer）

- `MAJOR.MINOR.PATCH`
- 0.x 阶段：MINOR 表示重大特性，PATCH 表示 bug fix
- 1.0 之后：严格 SemVer
- 开发版后缀：`0.2.0.dev0` / `0.2.0rc1`

### 8.2 发版前 checklist（每条必须打勾）

参见 [`governance/RUNBOOK.md`](governance/RUNBOOK.md) 的发版章节。简版：

```
[ ] python -m pytest -q  # 全绿
[ ] python scripts/acceptance_check.py  # 全绿
[ ] python scripts/acceptance_v02_stress.py  # 真实 LLM 验证
[ ] CHANGELOG 更新
[ ] README 更新（如有用户可见变化）
[ ] pyproject.toml 版本号更新
[ ] 所有 docs/*.md 与代码一致
[ ] git tag v0.x.0 && git push --tags
```

### 8.3 GitHub Release 模板

```markdown
## v0.2.0 - Hybrid Evidence Engine

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Breaking
- `--engine` flag removed, use `--llm-augment` instead

**Full changelog**: [CHANGELOG.md](CHANGELOG.md)
**Article**: [知乎 v2 文章](https://zhuanlan.zhihu.com/p/xxxxx)
```

---

## 9. 调试技巧

### 9.1 常见问题

**Q: LLM 引擎返回 EngineUnavailable**
- 检查 `DEEPSEEK_API_KEY` 是否设置
- 检查网络连通：`curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"`
- 看 `docs/archive/v0.2/stress_report.txt` 最后的 API_BOUNDARY 部分

**Q: 中文在 PowerShell 里显示乱码**
- 工具内部已用 UTF-8，PowerShell 管道（`|`）会把 stdout 转回 GBK
- 解决：直接交互运行，或写到文件 `> output.txt; type output.txt`
- CLI 已自动调用 `SetConsoleOutputCP(65001)`，命令行直接跑没问题

**Q: 测试在 CI 上 fail 但本地过**
- 可能依赖时区 / locale / 文件系统大小写
- 用 `pytest -v --tb=short` 看具体错
- 检查是否有依赖未声明（pyproject.toml）

### 9.2 调试 hybrid 证据合并

在 `stateprobe/detector.py` 的 `detect_readings` 加临时 print：

```python
for c in contributors:
    partial = c.contribute(prompt, baseline)
    print(f"[debug] {c.name} contributed:")
    for axis, srcs in partial.items():
        for s in srcs:
            print(f"  {axis.id} {s.direction:+d} strength={s.strength} conf={s.confidence}: {s.matched_text}")
```

调完删掉。

---

## 10. 性能边界

| 场景 | 期望延时 | 实测 |
|---|---|---|
| Static-only diagnose（无 LLM） | < 50 ms | ~ 5 ms |
| LLM-augmented diagnose | 1-3 s | 2.2 s（DeepSeek Chat） |
| HTML 报告生成 | < 200 ms | ~ 100 ms |
| 全套测试（unit + integration） | < 10 s | ~ 6 s |

如果有性能回归，先怀疑：
1. 正则编译是否在每次调用重新做（应该 module-level cache）
2. LLM 调用是否被同步阻塞
3. HTML 模板是否在循环里重复读盘

---

## 11. 不变性 / 千万别破

1. **`diagnose()` 默认行为永远不变**：不传任何 contributor 时等价于 v0.1（StaticRuleContributor + Structural）。
2. **空 prompt 永远返回 baseline 且 is_trivial=True**。
3. **任何 contributor 失败不能让 diagnose() 抛异常**（除非它是唯一的 contributor 且必需）。
4. **PollutionSource / AxisEvidence 字段只能加，不能删或改语义**——已发布的版本要兼容。
5. **8 个轴的语义不能改**——已发的文章和外部引用挂在这上面。

破坏这些 = 破坏向后兼容 = 必须升 MAJOR。

---

## 12. 进阶资源

- [ARCHITECTURE.md](ARCHITECTURE.md) - 架构总览
- [adr/009-hybrid-engine.md](adr/009-hybrid-engine.md) - hybrid 架构的完整决策依据
- [adr/decisions.md](adr/decisions.md) - 所有重大决策的简短记录
- [EVIDENCE_MODEL.md](EVIDENCE_MODEL.md) - 证据数据模型详解
- [governance/RUNBOOK.md](governance/RUNBOOK.md) - 运维 / 发版 / 平台发布 SOP

---

*这份文档跟代码一起进化。如果你改了架构或加了能力但没更新这里，未来的你会骂现在的你。*

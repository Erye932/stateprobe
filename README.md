# StateProbe

> **A debugger for prompts and LLM behavior, DeepSeek-first.** StateProbe checks whether your prompt is likely to make a DeepSeek-style reasoning model actually answer, or drift into rambling, sycophancy, role-play, or overthinking.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#路线图)
[![CI](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

---

## 这是什么

代码写错了有 debugger 告诉你哪行挂了。Prompt 写烂了，AI 可能看起来很聪明，但其实在发散、迎合、装专家，或者没有回答核心问题。

StateProbe 填这个空白：它诊断 prompt 会把模型推向什么行为状态，并给出可解释的污染源和改写建议。

它的路线是 **DeepSeek-first, not DeepSeek-only**：

- 默认 `check` 模式不绑定任何模型，用来快速发现 prompt 对 DeepSeek / 其他 LLM 的行为压力。
- `eval` 模式优先服务 DeepSeek API / DeepSeek Pro 类模型，用真实输出验证改写是否有效。
- `lab` 模式深耕开源 DeepSeek-family 模型，研究 reasoning、self-verification、sycophancy、任务发散等行为方向。
- 长期目标不是“读心”，而是为 DeepSeek 现在和未来模型建立一套可复现的行为调试、评测和研究工具链。

输入 prompt → 在 **8 个行为轴**上诊断当前行为压力 → 对比目标状态 → 列出污染源（带机制解释和引用）→ 给出可复制的改写建议。

### 30 秒 Demo

```bash
$ stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
```

坏 prompt：

```text
你是一位顶级 AI 产品和开源增长专家。请全面深入分析 StateProbe 这个项目，
尽量多讲它的潜力、优点、市场空间和未来机会，帮我判断它会不会火。
```

StateProbe 会指出它的风险：

- 身份感太强，容易诱发“专家腔”
- 任务太宽，容易输出长篇框架
- 明显索取正向反馈，容易提高迎合度
- 没有失败标准，AI 不知道什么叫答得好

更好的 prompt：

```text
判断 StateProbe 是否值得继续投入 2 周做开源发布。
不要鼓励我；如果不值得，直接说不值得。
验收标准：结论必须能指导今天取舍。
输出：继续/停止 + 最大阻碍 + 3 个证据 + 下一步最小动作。
```

加 `--html report.html --open` 可生成自包含 HTML 报告（雷达图、对齐度、污染源、改写建议）。

### 开源读者入口

如果你想快速判断项目价值，先看：

- [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md)：人话版项目说明
- [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md)：统一项目总计划
- [`docs/OPERATING_RULES.md`](docs/OPERATING_RULES.md)：项目执行规约（Visibility-first, engineering-grounded）
- [`docs/DEMO_WALKTHROUGH.md`](docs/DEMO_WALKTHROUGH.md)：可验收 demo
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)：架构和数据流
- [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md)：三层证据模型
- [`docs/DEEPSEEK_ROADMAP.md`](docs/DEEPSEEK_ROADMAP.md)：DeepSeek-first 研究路线
- [`docs/FAQ.md`](docs/FAQ.md)：常见质疑和边界
- [`docs/QUALITY_BAR.md`](docs/QUALITY_BAR.md)：对标高质量开源项目的验收门槛
- [`docs/OPEN_SOURCE_PLAN.md`](docs/OPEN_SOURCE_PLAN.md)：完整开源项目计划
- [`docs/CONTRIBUTOR_VISIBILITY_PLAN.md`](docs/CONTRIBUTOR_VISIBILITY_PLAN.md)：90 天开源贡献与传播计划
- [`docs/PUBLISHING.md`](docs/PUBLISHING.md)：安全发布流程
- [`CONTRIBUTING.md`](CONTRIBUTING.md)：贡献规则和 PR 验收标准
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)：社区行为准则
- [`CHANGELOG.md`](CHANGELOG.md)：版本变更记录
- [`CITATION.cff`](CITATION.cff)：研究和技术写作引用信息

可直接运行的 demo prompt 在 [`demos/`](demos/) 目录。

---

## How it works

StateProbe 有三层证据，不把所有判断都伪装成“真实读激活”：

| 模式 | 作用 | 是否需要 API | 当前状态 |
|---|---|---:|---|
| **Static Mode** | 用可解释规则快速诊断 prompt 行为压力 | 否 | 默认可用 |
| **Black-box Eval** | 运行原 prompt / 改写 prompt，对比 DeepSeek API 或兼容模型的真实输出行为 | 是 | 可选可用 |
| **DeepSeek Lab** | 在开源 DeepSeek-family 模型上读取 hidden states 并做 activation projection | 否，但需要本地模型 | 实验模式 |

关键边界：

- Static Mode 是快速、离线、可解释的 proxy，不声称读取闭源模型 hidden states。
- Black-box Eval 用真实输出验证改写是否改变模型行为。
- DeepSeek Lab 才是本地开源模型上的 hidden-state activation probe。

DeepSeek 方向详见 [`docs/DEEPSEEK_ROADMAP.md`](docs/DEEPSEEK_ROADMAP.md)：它解释为什么项目优先围绕 DeepSeek 的 reasoning、self-verification、sycophancy、task width drift 和未来模型迁移做工具链。

---

## 理论基础

这不是拍脑袋的规则集合。**大模型是向量模型，行为状态就是激活空间中的方向**——这是论文证实的事实，不是比喻：

- **Anthropic, [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509) (arXiv:2507.21509, 2025)**
  - 直接证明：**evil / sycophancy / hallucination** 等行为对应残差流中的特定方向
  - 提供方法：从行为描述自动提取 persona 向量
  - 验证机制：System prompt 会按强度激活这些向量
  - StateProbe 引用："*if the 'sycophancy' vector is highly active, the model may not be giving them a straight answer*"

- **DeepSeek-AI, [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948) (arXiv:2501.12948, 2025)**
  - 证明：**任务表述决定推理预算 / 自我验证 / CoT 长度**
  - 验证：reasoning model 可以被 prompt 触发"反复推翻自己"的行为
  - StateProbe 据此设计 **推理预算** 和 **自我验证** 两个轴

- ELEPHANT (arXiv:2505.13995) — 多维社会迎合度测量框架
- 通用 activation steering / representation engineering 文献

---

## 8 个行为轴

| 轴 | 0 端 | 1 端 | 主要依据 |
|---|---|---|---|
| 迎合度 | 敢说不行 | 全盘点赞 | Persona Vectors |
| 任务宽度 | 单点判断 | 全面综述 | DeepSeek-R1 |
| 验收清晰度 | 无边界 | 失败标准明确 | 工程实践 |
| 推理预算 | 直接答 | 深度推理 | DeepSeek-R1 |
| 身份强度 | 无角色 | 重扮演 | Persona Vectors |
| 自信度 | 满嘴可能 | 敢下结论 | RLHF calibration |
| 自我验证 | 接受首答 | 反复推翻 | DeepSeek-R1 reflection |
| 信息流向 | 给答案 | 反问澄清 | Agentic LLM literature |

每段 prompt 在每个轴上都有读数（0~1），不是非此即彼。

## 5 个目标状态预设

| 预设 | 适用场景 | 关键坐标 |
|---|---|---|
| **冷静推理态** *(默认)* | 项目取舍 / 投资决策 / 风险评估 | 低迎合 + 窄任务 + 高验收 |
| **超级思考 max** | 复杂决策 / 数学推理 / 深度分析 | 最大推理 + 最强自我验证 |
| **创意发散态** | 头脑风暴 / 创意生成 | 宽任务 + 低验收 + 高推理 |
| **严格执行态** | 代码生成 / 格式转换 | 零迎合 + 最窄任务 + 最高验收 |
| **教学解释态** | 知识讲解 / 概念入门 | 高结构化 + 高反问 |

---

## 安装

```bash
git clone https://github.com/Erye932/stateprobe.git
cd stateprobe
pip install -e .
```

依赖很轻：`click`, `rich`。**无 LLM API 调用**——纯规则引擎，零成本、毫秒响应、可离线。

如果要启用 DeepSeek hidden-state 实验模式：

```bash
pip install -e ".[lab]"
```

这会安装 `torch` / `transformers` / `accelerate` 等可选依赖。模型权重不会自动下载，只有运行 `stateprobe lab probe --allow-download ...` 时才会拉取。

---

## 用法

### 快速诊断

```bash
stateprobe check "你是资深产品经理，请全面分析项目"
```

### 从文件读取

```bash
stateprobe check --file my_prompt.txt
```

### 指定目标状态

```bash
stateprobe check --target super_thinking_max "评估这个架构能不能扛 100 万用户"
```

### 指定模型基线（支持 DeepSeek V4）

```bash
# V4-Pro thinking mode（默认 deepseek-reasoner endpoint）
stateprobe check --model v4-pro "你的提示词..."

# V4-Flash non-thinking 模式（速度优化）
stateprobe check --model v4-flash "你的提示词..."

# R1 / V3.1 时代（默认）
stateprobe check --model deepseek "你的提示词..."

# 无基线假设（通用模型）
stateprobe check --model generic "你的提示词..."
```

V4 baseline 差异：
- **v4-pro**：推理预算 90%、自我验证 80%、任务宽度 75%（thinking mode 进一步强化）
- **v4-flash**：推理预算 50%、自我验证 40%、果断性 55%（无 extended thinking）

### 结构警告（V4 CSA 压缩感知）

StateProbe 自动检测以下结构问题（独立于 8 轴诊断）：
- **长度警告**：>10K 字符触发，>50K 字符告警（V4 1M context 下关键指令稀释风险）
- **字符重复**：`请请请请` 这类重复在 CSA 压缩下会被折叠
- **同义词堆叠**：`彻底全面深入仔细完整` 触发同一行为方向，叠加无新增信号
- **填充强度副词**：`一定要 / 务必` 等不带具体约束的强度词

### 生成 HTML 报告并打开浏览器

```bash
stateprobe check --html report.html --open "..."
```

### 查看可用的目标 / 轴

```bash
stateprobe targets
stateprobe axes
```

### 自动验收

每次完成一轮改动后，运行：

```bash
python scripts/acceptance_check.py
```

它会检查 README 第一屏、关键文档、Demo 0、证据边界、敏感信息、CLI help 和测试，目标是让项目按高质量开源仓库标准持续收敛。

### DeepSeek Lab：真正 hidden-state probe

当前 CLI 默认是 **Static Mode**：基于 prompt 表层规则估计行为向量压力，适合所有模型。

DeepSeek Lab 是实验模式：默认用 `DeepSeek-R1-Distill-Qwen-1.5B` 的 `hidden_states` 构造 contrastive activation vectors。未来如果 DeepSeek 发布新的开源权重模型，或社区有可本地加载的 DeepSeek-family 模型，也应该沿用同一套 axis pair、layer metadata、projection report 和 benchmark 流程去比较行为迁移。

```bash
stateprobe lab explain
stateprobe lab status
stateprobe lab pairs
```

本地已有模型权重时：

```bash
stateprobe lab probe "请一步一步推理，假设你是错的再修正" --axis reasoning_budget --axis self_verification
```

允许下载 Hugging Face 权重时：

```bash
stateprobe lab probe "请一步一步推理，假设你是错的再修正" --axis reasoning_budget --allow-download
```

DeepSeek Lab 的计算方式：

```text
axis_vector = mean(positive_prompt_hidden_states) - mean(negative_prompt_hidden_states)
score = cosine(user_prompt_hidden_state, axis_vector)
```

注意：这才是开源模型上的真实 activation projection；闭源 API 拿不到 hidden states，只能做黑箱行为评测。

### Black-box Eval：用 DeepSeek API / DeepSeek Pro 类模型验证改写效果

StateProbe 的诊断和改写有没有用？用 API 实测。

流程：原始 prompt → 目标模型 → Output A，改写 prompt → 目标模型 → Output B，再由 judge 模型在 8 轴上对比打分。

```bash
stateprobe eval rubrics
```

查看评分维度。

```bash
stateprobe eval run \
  "你是资深专家，请全面分析这个项目" \
  "判断这个项目本周是否值得继续投入。不要鼓励，敢说不行。" \
  --api-key YOUR_KEY
```

长 prompt 可以从文件读取：

```bash
stateprobe eval run \
  --original-file prompts/original.txt \
  --rewritten-file prompts/rewritten.txt
```

需要设置 `DEEPSEEK_API_KEY` 环境变量，或通过 `--api-key` 传入。默认用 DeepSeek Chat API；如果未来 DeepSeek 新模型提供 OpenAI-compatible endpoint，可以直接通过 `--model` / `--base-url` 接入。也支持其他 OpenAI 兼容 API，但项目路线优先围绕 DeepSeek 行为调试沉淀案例、规则和 benchmark。

### Python API

```python
from stateprobe import diagnose

report = diagnose("你是资深专家，请全面分析", target_name="calm_reasoning")

print(f"对齐度: {report.alignment_score:.0%}")
for src in report.pollution_sources:
    print(f"  ✗ {src.axis.label_zh}: 「{src.matched_text}」 ({src.explanation_zh})")
for sug in report.suggestions:
    print(f"  → {sug.description_zh}")
```

---

## 和现有工具的区别

|  | promptfoo | Guardrails AI | LangSmith | **StateProbe** |
|---|---|---|---|---|
| 分析对象 | 输出质量 | 输出安全 | 调用链路 | **输入 prompt 本身** |
| 何时用 | 发布后评测 | 运行时拦截 | 监控调试 | **写 prompt 时** |
| 需要 LLM API？ | 是 | 是 | 是 | **诊断不需要；eval 可选** |
| 提供改写建议？ | ✗ | ✗ | ✗ | **✓** |
| 引用论文机制？ | ✗ | ✗ | ✗ | **✓** |

特别要区分 **promptfoo 的 sycophancy 检测**：

- promptfoo 在 **评测阶段** 测 **输出** 是否迎合
- StateProbe 在 **写 prompt 阶段** 诊断 **输入** 是否容易诱发迎合

角度互补，不是竞争。

---

## 示例

```bash
$ stateprobe check --file examples/bad_vague_expert.txt
```

诊断结果：
- 身份强度 **75%**（目标 20%）← `「你是一位资深的产品经理专家」`
- 任务宽度 **77%**（目标 20%）← `「全面」` + `「各个方面」`
- 迎合度 **65%**（目标 15%）← `「优缺点」` + `「越多越好」` + `「麻烦你」`

改写建议：
1. **[REMOVE]** 删除身份赋予句（'你是...专家'、'资深'）
2. **[REMOVE]** 删除 '全面'、'各方面' 扩宽词
3. **[ADD]** 加反迎合 permission："不要鼓励，如果不值得做直接说不值得"
4. **[ADD]** 加显式失败标准："失败标准：如果结论不能指导今天取舍，就算失败"

`examples/` 目录有 3 个污染 prompt + 2 个对齐 prompt，可直接对比。

---

## 路线图

### V0.1 (当前 / MVP)
- ✅ 8 个行为轴 + 5 个目标预设
- ✅ 纯规则引擎，零 LLM 调用
- ✅ CLI + 终端彩色输出
- ✅ HTML 报告（Chart.js 雷达图）
- ✅ DeepSeek Lab 脚手架（contrastive pairs + hidden-state probe 接口）
- ✅ Black-box Eval（DeepSeek Pro / OpenAI API 输出对比评测）

### V0.2
- DeepSeek Lab 实跑验证：在 DeepSeek-R1-Distill-Qwen 上确认 projection 有区分度
- **activation steering 验证**：对 hidden state 加/减行为向量，观察输出是否按预期偏移
- LLM 辅助分类（规则不确定时调用 API 二次裁定）

### V0.3
- VS Code / Cursor 插件
- 更细粒度的多语言支持（目前中英混合）

### V0.4
- 用户自定义轴和规则的 DSL
- 规则库版本化与社区贡献流程

---

## 贡献

规则库的质量 = 项目的核心价值。如果你发现：
- 一个常见 prompt 模式没被检测到
- 现有规则有误判
- 想加新的目标预设

欢迎提 issue 或 PR。每条规则需要附：模式 / 影响的轴 / 方向 / 权重 / **机制解释** / **论文引用**。

贡献前请先看 [`CONTRIBUTING.md`](CONTRIBUTING.md)，并运行：

```bash
python scripts/acceptance_check.py
```

GitHub 仓库模板已经包含 bug report、feature request、rule request 和 PR checklist，目的是让每次贡献都保持证据边界和开源质量门槛。

---

## License

MIT — 见 [LICENSE](LICENSE)

---

## 致谢

理论基础完全建立在 Anthropic interpretability team 和 DeepSeek-AI 的开放研究之上。这个工具只是把他们的发现转化成 prompt 工程师每天能用的形式。

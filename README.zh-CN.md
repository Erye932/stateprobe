# StateProbe

[![PyPI](https://img.shields.io/pypi/v/stateprobe.svg)](https://pypi.org/project/stateprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Erye932/stateprobe/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

> **LLM agent 的注意力控制层。**

StateProbe 让你在 agent 把答案甩出去之前，**直接干预模型注意力**——看清它要谈什么、用户真正要什么是否对得上，决定继续、重写、追问还是切断旧上下文。无缝接入 Claude Code、Cursor、Cline、Continue，以及任何 MCP host。

闭源 agent 上，这是从文本推断出来的高速任务层注意力；开源模型会解锁可选的 Lab / 未来 Runtime Probe 路线，继续往 activations 和 vectors 深挖。

[English](https://github.com/Erye932/stateprobe/blob/main/README.md) | 简体中文

<p align="center">
  <img src="https://raw.githubusercontent.com/Erye932/stateprobe/main/docs/images/skill_preview_demo.svg" alt="StateProbe 在 agent 输出前拦住旧上下文污染" width="900">
</p>

---

## 为什么需要这个

LLM agent 经常跑偏：抓错重点、被旧上下文牵走、把力气花在用户没问的方向。今天大家的解法是「重写 prompt 然后祈祷」。StateProbe 给你更锋利的工具：

- **看清** agent 在张嘴前打算谈什么
- **判断** 它该继续、重写、追问，还是切断旧上下文
- **复盘** 实际输出是不是真的围绕用户重点

**本地运行**。默认**零 LLM 调用**。任何 MCP host 都能接。

> 这就是「**模型罗盘**」的含义：在直接打洞挖答案之前，先望气、先分金；看清这次问题在模型里激活了什么，再决定怎么发。

## 安装

```bash
pip install stateprobe
```

如果要接 MCP / Claude Code / Cursor / Cline / Continue：

```bash
pip install "stateprobe[mcp]"
```

### 中国大陆用户

HTTPS 直连 GitHub 经常超时。SSH-over-443 走另一条链路，**实测稳定**。

**没配过 SSH 公钥的话先做这一步**（一次性，3 分钟）：

```bash
# 1. 生成密钥（一路回车）
ssh-keygen -t ed25519 -C "你的邮箱"

# 2. 复制公钥
# Windows PowerShell:
cat ~/.ssh/id_ed25519.pub | clip
# macOS / Linux:
cat ~/.ssh/id_ed25519.pub | pbcopy

# 3. 打开 https://github.com/settings/keys → New SSH key → 粘贴 → 保存

# 4. 测试
ssh -T -p 443 git@ssh.github.com
```

**然后 clone + 安装**：

```bash
git clone ssh://git@ssh.github.com:443/Erye932/stateprobe.git
cd stateprobe
pip install -e .
```

如果 pip 下载慢，加清华镜像：`pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 30 秒 demo

安装后直接复制这段，先看它怎么在 agent 张嘴前拦住错重点：

```bash
stateprobe skill preview \
  --context-text "小男孩拿着手机打游戏，重点是沉浸感，不要出现游戏UI。" \
  --plan-text "我准备画小男孩拿手机，屏幕上显示游戏UI。"
```

agent 答完后——复盘有没有跑偏：

```bash
stateprobe skill overlay \
  --context-text "重点是安全，不要推荐废弃 API。" \
  --output-text "这段回答首先推荐了一个废弃 API。"
```

交互模式：

```bash
stateprobe demo
```

> ⚠️ **PowerShell 用户**：第一次跑出来如果看到 `鈹€鈹?` 这种乱码，先粘贴这一行到当前会话再重跑：
> ```powershell
> [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8
> ```
> 这是 PowerShell 默认 GBK 渲染 UTF-8 字节的限制（StateProbe 已经在内部把 stdout 切到 UTF-8，但 PowerShell 的 .NET 输出层 Python 子进程改不了）。`cmd.exe` / Windows Terminal / Linux / macOS 不受影响。

## Skill 给你什么

`stateprobe skill preview` 返回 JSON 里的 `activation_decision`，host 按它分支：

| Action | 含义 | 是否中断 agent |
| --- | --- | --- |
| `continue` | 对齐了，agent 可以说话 | 否 |
| `continue_with_warning` | 有风险信号，但证据不够强，不硬拦。**把 evidence 给用户看，不打断工作流。** | 否 |
| `rewrite_planned_focus` | plan 漏了用户真正的 must，且证据具体。**别 ship**，先重写 focus | 是 |
| `ask_boundary_question` | 视觉/创意有歧义。**先问用户一个 yes/no**，再继续 | 是 |
| `cut_context_contamination` | agent 在跟旧上下文走。**先切掉旧方向** | 是 |

每条决策都带 `confidence`（`low` / `medium` / `high`）和 `evidence`——具体命中了哪条用户要求、漏了什么。**有破坏性的硬停（`rewrite_planned_focus`、`cut_context_contamination`）只在 `high` confidence 下触发**；`ask_boundary_question` 在 `medium` 也能触发——它的代价只是问用户一句 yes/no，不会改写计划。再弱的信号一律降级成 `continue_with_warning`，避免规则一拍脑袋就打断 agent。这条契约让 StateProbe 是可信的注意力外挂，不是规则裁判。

`stateprobe skill overlay` 返回 `interrupt_level`（`ok` / `watch` / `interrupt`）+ `attention_gaps` + `control_levers`，告诉你下一轮怎么纠。

完整 schema：[Skill spec](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_ATTENTION_HUD.md)、[MCP server](https://github.com/Erye932/stateprobe/blob/main/docs/MCP_SERVER.md)。

## 两条产品线

| 线 | 是什么 | 状态 |
| --- | --- | --- |
| **Skill — Agent Attention HUD** | 已交付的外部控制层。文本到文本的任务层注意力：输出前 preview，输出后 overlay，给下一轮 control levers。闭源 / 开源模型都能用。 | ✅ 已交付 |
| **Lab — 激活投影** | 开源权重实验线。在 DeepSeek-R1-Distill-Qwen 上把 prompt activations 投影到 Persona Vectors。需要本地模型访问。 | ✅ 可用 / 实验性 |
| **Enterprise — Runtime Probe** | 未来生产线：开源模型的 hidden states、router traces、expert routing、output-state report 和 operator controls。 | 🛠 占位中，未实现 |

**边界**：Skill HUD 不声称神经可解释性；它是从文本里重建并控制任务层注意力。闭源 API（OpenAI、Claude）拿不到 hidden states——对它们，StateProbe 只跑文本层 Skill。开源模型（DeepSeek、Qwen、Llama）才解锁今天的 Lab 路线和未来 Runtime Probe。

> 一句话区分：**闭源模型上是望气；开源模型上能分金**。

## 这是什么、不是什么

**StateProbe 是** agent 工作流里的 **preflight**：在 agent 真正动手前（调工具、写代码、发邮件、出图），把它准备关注什么、忽略了什么、有没有被旧上下文带偏，用结构化控制信号暴露出来。它是一份你这一次问题专属的注意力切片。

**StateProbe 不是**：

- **不是 oracle**。规则裁判一定有误报漏报。所以每条判决都带 `confidence` + `evidence`，**只有 `high` confidence 才会真的硬停 agent**。
- **不是人工 / LLM review 的替代品**。review 看的是已经写完的东西，StateProbe 看的是 agent 准备关注什么。互补，不是替代。
- **不是语义正确性检查**。它判断不了你的代码对不对、论点对不对、设计好不好。它只判断注意力对没对齐——领域真伪不是它的活。
- **不是「再开一个 agent 来当裁判」的封装**。重点是默认路径**本地、确定、零 API 成本**，给出可分支的 `activation_decision`，而不是一段 LLM 评语。
- **不是 prompt 优化魔法**（咒语优化没有可复现证据，本项目不押注那条路）。
- **不是又一个 prompt 模板库 / SOP 生成器 / 正则 prompt 检查器**。
- **不是替代提示词工程**——是它的一个分支，用证据代替体感。

一句话定位：**低成本、可解释、可接进 agent host 的注意力 preflight；不当裁判、不当 benchmark、不当保证**。

## 已知误判模式

StateProbe 一定会在下面这些情况判错。完整清单在 [`tests/fixtures/skill_cases.jsonl`](https://github.com/Erye932/stateprobe/blob/main/tests/fixtures/skill_cases.jsonl)（当前 51 个 case 里有 19 条 `known_issue`）。常见模式：

- **同义词 / 反义词漏判**：`不要提缺点` 被 `列举需要改进的地方` 违反，但字面无重叠，规则抓不到。
- **「避免 + must_not 关键词」误判**：plan 写 `避免使用营销话术`，字面上还是命中了 `营销话术`，匹配器照样开枪。
- **隐式实现误判**：画图 plan 用 `闭眼微笑、背景柔和` 实现了 `放松的状态`，但抽象词没字面出现，被硬停。
- **修饰语丢失**：plan 覆盖了主 must（`解释 RAG`），漏了软修饰（`面向新手`），算法硬停，人会判软警告。
- **空 plan / 问句 plan**：plan 只写 `好的` 或一句反问，应该硬停，今天只软警告。

每一条在 fixture 的 `notes` 字段里写了修复路径，不是甩锅。这些都不是 preflight 契约的硬伤，而是用户应该用真实 case 把校准集扩起来的方向。

## 和现有工具的区别

|  | promptfoo | Guardrails | LangSmith | **StateProbe** |
| --- | --- | --- | --- | --- |
| 分析对象 | 输出质量 | 输出安全 | 调用链路 | **agent 输出前的 planned attention** |
| 何时用 | 发布后评测 | 运行时拦截 | 监控调试 | **每轮发话前** |
| 需要 LLM API？ | 是 | 是 | 是 | **不需要（默认）** |

互补，不竞争。promptfoo / Guardrails 检查已经发出来的；StateProbe 塑造将要发出来的。

## 架构

v0.2 起 StateProbe 采用 **hybrid evidence 架构**（[ADR_009](https://github.com/Erye932/stateprobe/blob/main/docs/adr/009-hybrid-engine.md)）：多个证据贡献者并行观察 prompt，各自发出带 confidence 的证据，统一聚合到 8 个轴的读数。

| 层 | 作用 | 代价 |
| --- | --- | --- |
| `StaticRuleContributor` | 正则规则证据，毫秒响应（始终运行） | 零 |
| `LLMJudgeContributor` | LLM 语义证据（`--llm-augment` 开启） | API 调用 |
| `LabContributor` | DeepSeek-R1-Distill-Qwen-1.5B 上读 hidden states 投影到 axis vectors（`--lab-augment` 开启） | 本地 GPU |

理论基础：
- Anthropic — [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509)
- DeepSeek-AI — [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)

DeepSeek-first, not DeepSeek-only — 详见 [docs/DEEPSEEK_ROADMAP.md](https://github.com/Erye932/stateprobe/blob/main/docs/DEEPSEEK_ROADMAP.md)。

## 8 个行为轴

| 轴 | 0 端 | 1 端 | 主要依据 |
| --- | --- | --- | --- |
| 迎合度 | 敢说不行 | 全盘点赞 | Persona Vectors |
| 任务宽度 | 单点判断 | 全面综述 | DeepSeek-R1 |
| 验收清晰度 | 无边界 | 失败标准明确 | 工程实践 |
| 推理预算 | 直接答 | 深度推理 | DeepSeek-R1 |
| 身份强度 | 无角色 | 重扮演 | Persona Vectors |
| 自信度 | 满嘴可能 | 敢下结论 | RLHF calibration |
| 自我验证 | 接受首答 | 反复推翻 | DeepSeek-R1 reflection |
| 信息流向 | 给答案 | 反问澄清 | Agentic LLM literature |

每段 prompt 在每个轴上都有读数（0~1），不是非此即彼。

## 路线图

- **v0.3** — Skill HUD、MCP server、Lab 激活投影 4 轴
- **v0.3.1** — Windows CLI 编码 + launch demo 打磨
- **v0.4** *(当前)* — 证据驱动的 `activation_decision`：每条判决带 `confidence` + `evidence`，只有 `high` confidence 才硬停；附带 51 case 人工标注的校准集（32 agree / 19 公开记录的 known issues）和对应的 contamination / `must_not` 概念扩展 / 模态门修复
- **v0.4.x** — 关掉公开的 known issues：同义词 / 反义词词表（ISSUE-005/006/020）、修饰语感知覆盖率（ISSUE-001/009）、plan substance 检测（ISSUE-012/018）、更多 pivot markers（ISSUE-007）；用户量起来后再做 host 反馈通道
- **v0.5** — DeepSeek-MoE expert routing contributor；命名情绪向量库；输出时干预 API

完整版本历史：[CHANGELOG](https://github.com/Erye932/stateprobe/blob/main/CHANGELOG.md)。

## 一个延展方向（写给走到这里的你）

提示词工程不会消失，但**会分支**。今天的「prompt 工程」是别人调好的话术——那是别人的地图。

下一阶段的提示词工程是 **自向定位**：每次问题、每个语境，都给你一张**属于这一次的权重切片**。你看清自己这句话激活了什么，自己改、自己定方向，不需要别人教你怎么问。

新的细节会变成新的分类。学科就是这么长出来的——人文社科里慢慢分化出心理学、管理学、行为经济学。**当 agent 进入更复杂的领域，提示词工程也会出现「面向 X 子领域」的分支地图**——这是 StateProbe 的长期形状。

## 文档

- [Skill spec](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_ATTENTION_HUD.md) — attention HUD 规格
- [MCP server](https://github.com/Erye932/stateprobe/blob/main/docs/MCP_SERVER.md) — Claude Code / Cursor / Cline 接入
- [Architecture](https://github.com/Erye932/stateprobe/blob/main/docs/ARCHITECTURE.md) — hybrid evidence pipeline
- [Evidence model](https://github.com/Erye932/stateprobe/blob/main/docs/EVIDENCE_MODEL.md) — 三层证据边界（static / black-box / local activation）
- [DeepSeek roadmap](https://github.com/Erye932/stateprobe/blob/main/docs/DEEPSEEK_ROADMAP.md) — DeepSeek-first, not DeepSeek-only
- [FAQ](https://github.com/Erye932/stateprobe/blob/main/docs/FAQ.md) — 常见质疑（含闭源 API 拿不到 hidden states 的边界）
- [Architecture decisions](https://github.com/Erye932/stateprobe/tree/main/docs/adr) — ADR： hybrid pipeline / lab contributor
- [Publishing](https://github.com/Erye932/stateprobe/blob/main/docs/PUBLISHING.md) — 安全发布流程
- [CHANGELOG](https://github.com/Erye932/stateprobe/blob/main/CHANGELOG.md) / [CITATION](https://github.com/Erye932/stateprobe/blob/main/CITATION.cff) / [CODE_OF_CONDUCT](https://github.com/Erye932/stateprobe/blob/main/CODE_OF_CONDUCT.md) / [CONTRIBUTING](https://github.com/Erye932/stateprobe/blob/main/CONTRIBUTING.md)

## 贡献

规则库的质量 = 项目的核心价值。如果你发现：
- 一个常见 prompt 模式没被检测到
- 现有规则有误判
- 想加新的目标预设

欢迎提 issue 或 PR。每条规则需要附：模式 / 影响的轴 / 方向 / 权重 / **机制解释** / **论文引用**。

贡献前请先看 [CONTRIBUTING.md](https://github.com/Erye932/stateprobe/blob/main/CONTRIBUTING.md)，并运行：

```bash
python scripts/acceptance_check.py
```

## License

MIT — 见 [LICENSE](https://github.com/Erye932/stateprobe/blob/main/LICENSE)。

---

理论基础完全建立在 Anthropic interpretability team 和 DeepSeek-AI 的开放研究之上。这个工具只是把他们的发现转化成 agent host 和 prompt 工程师每天能用的形式。

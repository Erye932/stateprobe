# StateProbe

[![PyPI](https://img.shields.io/pypi/v/stateprobe.svg)](https://pypi.org/project/stateprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

> **LLM agent 的注意力控制层。**

StateProbe 让你在 agent 把答案甩出去之前，**直接干预模型注意力**——看清它要谈什么、用户真正要什么是否对得上，决定继续、重写、追问还是切断旧上下文。无缝接入 Claude Code、Cursor、Cline、Continue，以及任何 MCP host。

[English](README.md) | 简体中文

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

agent 张嘴前——预览它打算谈什么：

```bash
stateprobe skill preview \
  --context-text "小男孩拿着手机打游戏，重点是沉浸感，不要出现游戏UI。" \
  --plan-text "我准备画小男孩拿手机，屏幕上显示游戏UI。"
```

agent 答完后——复盘有没有跑偏：

```bash
stateprobe skill overlay \
  --context examples/skill_attention_context.txt \
  --output examples/skill_attention_output.txt
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

| Action | 含义 |
| --- | --- |
| `continue` | 对齐了，agent 可以说话 |
| `rewrite_planned_focus` | plan 漏了用户真正的 must。**别 ship**，先重写 focus |
| `ask_boundary_question` | 视觉/创意有歧义。**先问用户一个 yes/no**，再继续 |
| `cut_context_contamination` | agent 在跟旧上下文走。**先切掉旧方向** |

`stateprobe skill overlay` 返回 `interrupt_level`（`ok` / `watch` / `interrupt`）+ `attention_gaps` + `control_levers`，告诉你下一轮怎么纠。

完整 schema：[Skill spec](docs/SKILL_ATTENTION_HUD.md)、[MCP server](docs/MCP_SERVER.md)。

## 两条产品线

| 线 | 是什么 | 状态 |
| --- | --- | --- |
| **Skill — Agent Attention HUD** | 外部控制层。文本层 task attention。闭源 / 开源模型都能用。 | ✅ 已可用 |
| **Lab — 激活投影** | 在开源 DeepSeek-R1-Distill-Qwen 上把 prompt 投影到 Persona Vectors。可选启用。 | ✅ 已可用 |
| **Enterprise — Runtime Probe** | 长期方向：开源模型的 hidden states / router traces / expert routing。 | 🛠 占位中，未实现 |

**边界**：闭源 API（OpenAI、Claude）拿不到 hidden states——对它们，StateProbe 只跑文本层 Skill。开源模型（DeepSeek、Qwen、Llama）才解锁 Lab 层。

> 一句话区分：**闭源模型上是望气；开源模型上能分金**。

## 这是什么、不是什么

**StateProbe 是**：
- agent 输出前的注意力控制层
- 每次问题给你一份属于这一次的权重切片
- 让你「自向定位」——看清这次激活了什么，自己改、自己调，不靠别人的 prompt 模板

**StateProbe 不是**：
- 不是又一个 prompt 模板库
- 不是 SOP 生成器
- 不是 prompt 优化魔法（咒语优化没有可复现证据，本项目不押注那条路）
- 不是简单正则 prompt 检查器
- **不是替代提示词工程**——是它的一个分支，用证据代替体感

## 和现有工具的区别

|  | promptfoo | Guardrails | LangSmith | **StateProbe** |
| --- | --- | --- | --- | --- |
| 分析对象 | 输出质量 | 输出安全 | 调用链路 | **agent 输出前的 planned attention** |
| 何时用 | 发布后评测 | 运行时拦截 | 监控调试 | **每轮发话前** |
| 需要 LLM API？ | 是 | 是 | 是 | **不需要（默认）** |

互补，不竞争。promptfoo / Guardrails 检查已经发出来的；StateProbe 塑造将要发出来的。

## 架构

v0.2 起 StateProbe 采用 **hybrid evidence 架构**（[ADR_009](docs/adr/009-hybrid-engine.md)）：多个证据贡献者并行观察 prompt，各自发出带 confidence 的证据，统一聚合到 8 个轴的读数。

| 层 | 作用 | 代价 |
| --- | --- | --- |
| `StaticRuleContributor` | 正则规则证据，毫秒响应（始终运行） | 零 |
| `LLMJudgeContributor` | LLM 语义证据（`--llm-augment` 开启） | API 调用 |
| `LabContributor` | DeepSeek-R1-Distill-Qwen-1.5B 上读 hidden states 投影到 axis vectors（`--lab-augment` 开启） | 本地 GPU |

理论基础：
- Anthropic — [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509)
- DeepSeek-AI — [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)

DeepSeek-first, not DeepSeek-only — 详见 [docs/DEEPSEEK_ROADMAP.md](docs/DEEPSEEK_ROADMAP.md)。

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

- **v0.3** *(当前)* — Skill HUD、MCP server、Lab 激活投影 4 轴
- **v0.3.1** — 补齐剩余 4 轴；embedding contributor 离线兜底；VS Code / Cursor 插件
- **v0.4** — DeepSeek-MoE expert routing contributor
- **v0.5** — 命名情绪向量库；输出时干预 API

完整计划：[project plan](docs/governance/PROJECT_PLAN.md)、[open-source plan](docs/governance/OPEN_SOURCE_PLAN.md)、[CHANGELOG](CHANGELOG.md)。

## 一个延展方向（写给走到这里的你）

提示词工程不会消失，但**会分支**。今天的「prompt 工程」是别人调好的话术——那是别人的地图。

下一阶段的提示词工程是 **自向定位**：每次问题、每个语境，都给你一张**属于这一次的权重切片**。你看清自己这句话激活了什么，自己改、自己定方向，不需要别人教你怎么问。

新的细节会变成新的分类。学科就是这么长出来的——人文社科里慢慢分化出心理学、管理学、行为经济学。**当 agent 进入更复杂的领域，提示词工程也会出现「面向 X 子领域」的分支地图**——这是 StateProbe 的长期形状。

## 文档

- [Skill spec](docs/SKILL_ATTENTION_HUD.md) — attention HUD 规格
- [MCP server](docs/MCP_SERVER.md) — Claude Code / Cursor / Cline 接入
- [Architecture](docs/ARCHITECTURE.md) — hybrid evidence pipeline
- [Evidence model](docs/EVIDENCE_MODEL.md) — 三层证据边界（static / black-box / local activation）
- [DeepSeek roadmap](docs/DEEPSEEK_ROADMAP.md) — DeepSeek-first, not DeepSeek-only
- [FAQ](docs/FAQ.md) — 常见质疑（含闭源 API 拿不到 hidden states 的边界）
- [Quality bar](docs/governance/QUALITY_BAR.md) — 10k-star reference 标准
- [Operating rules](docs/governance/OPERATING_RULES.md) — Visibility-first, engineering-grounded, five gates
- [Visibility plan](docs/governance/CONTRIBUTOR_VISIBILITY_PLAN.md) — 90-day strategy
- [Open-source plan](docs/governance/OPEN_SOURCE_PLAN.md) — 完整开源项目计划
- [Project plan](docs/governance/PROJECT_PLAN.md) — 项目北极星与版本路线
- [Publishing](docs/PUBLISHING.md) — 安全发布流程
- [CHANGELOG](CHANGELOG.md) / [CITATION](CITATION.cff) / [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) / [CONTRIBUTING](CONTRIBUTING.md)

## 贡献

规则库的质量 = 项目的核心价值。如果你发现：
- 一个常见 prompt 模式没被检测到
- 现有规则有误判
- 想加新的目标预设

欢迎提 issue 或 PR。每条规则需要附：模式 / 影响的轴 / 方向 / 权重 / **机制解释** / **论文引用**。

贡献前请先看 [CONTRIBUTING.md](CONTRIBUTING.md)，并运行：

```bash
python scripts/acceptance_check.py
```

## License

MIT — 见 [LICENSE](LICENSE)。

---

理论基础完全建立在 Anthropic interpretability team 和 DeepSeek-AI 的开放研究之上。这个工具只是把他们的发现转化成 agent host 和 prompt 工程师每天能用的形式。

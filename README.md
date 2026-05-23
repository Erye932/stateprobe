# StateProbe

[![PyPI](https://img.shields.io/pypi/v/stateprobe.svg)](https://pypi.org/project/stateprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

> **The attention layer for LLM agents.**

Your agent already drifted — wrong focus, stale context, confidently editing files you never asked about. StateProbe catches it **before** the agent ships the answer. Works with **Claude Code**, **Cursor**, **Cline**, **Continue**, and any MCP host.

English | [简体中文](README.zh-CN.md)

---

## Why

LLM agents drift. They miss the user's actual point, get steered by stale context, or burn cycles on the wrong subtopic. Today's fix is "rewrite the prompt and pray." StateProbe gives you a sharper tool:

- **See** what the agent is about to focus on, before it answers
- **Decide** to continue, rewrite the focus, ask a boundary question, or cut stale context
- **Audit** the actual output afterwards and surface drift

Runs **locally**. Costs **zero LLM tokens** by default. Plugs into any MCP host.

## Install

```bash
pip install stateprobe
```

For MCP integration (Claude Code, Cursor, Cline, Continue):

```bash
pip install "stateprobe[mcp]"
```

For activation projection on open-source DeepSeek (optional):

```bash
pip install "stateprobe[lab]"
```

## 30-second demo

Before the agent answers, preview its planned focus:

```bash
stateprobe skill preview \
  --context-text "Focus on safety; do not include deprecated APIs." \
  --plan-text "I will list deprecated APIs and explain why they are unsafe."
```

After the agent answers, audit alignment with user requirements:

```bash
stateprobe skill overlay \
  --context examples/skill_attention_context.txt \
  --output examples/skill_attention_output.txt
```

Or run the legacy prompt diagnostic, with the included
[`smart_but_not_answering`](demos/smart_but_not_answering) demo:

```bash
stateprobe demo
```

## What it gives back

`stateprobe skill preview` returns a JSON `activation_decision` — your agent host branches on it:

| Action | Meaning |
| --- | --- |
| `continue` | Aligned. Agent can speak. |
| `rewrite_planned_focus` | Plan misses user's actual must. **Don't ship.** Rewrite focus first. |
| `ask_boundary_question` | Visual / creative ambiguity. **Ask the user one yes/no first.** |
| `cut_context_contamination` | Agent is following stale context. **Cut the old direction first.** |

`stateprobe skill overlay` returns an `interrupt_level` (`ok` / `watch` / `interrupt`) plus `attention_gaps` and `control_levers` for the next turn.

Full schemas: [Skill spec](docs/SKILL_ATTENTION_HUD.md), [MCP server](docs/MCP_SERVER.md).

## Two product lines

| Line | What | Status |
| --- | --- | --- |
| **Skill — Agent Attention HUD** | External control layer. Text-to-text task attention. Works with closed and open models. | ✅ Available |
| **Lab — Activation Projection** | Projects prompt activations onto Persona Vectors on open-source DeepSeek-R1-Distill-Qwen. Opt-in. | ✅ Available |
| **Enterprise — Runtime Probe** | Future direction: hidden states, router traces, expert routing on open-source models. | 🛠 Not yet implemented |

**Boundary**: closed-source APIs (OpenAI, Claude) cannot expose hidden states — for them, StateProbe runs the text-level Skill layer only. Open-source models (DeepSeek, Qwen, Llama) unlock the Lab layer. OpenAI/Claude 物理上读不到 hidden states; the Lab layer requires open weights.

## How it differs

|  | promptfoo | Guardrails AI | LangSmith | **StateProbe** |
| --- | --- | --- | --- | --- |
| Analyzes | Output quality | Output safety | Call traces | **Agent's planned attention before output** |
| When | After release | Runtime | Production | **Before each turn** |
| LLM API needed | Yes | Yes | Yes | **No (default)** |

Complementary, not competitive. promptfoo / Guardrails check what came out; StateProbe shapes what's about to come out.

## Architecture

Hybrid evidence pipeline ([ADR_009](docs/adr/009-hybrid-engine.md)): independent contributors emit confidence-weighted evidence, aggregated into 8 behavior axes. Static rules are always on (zero cost); the LLM and Lab layers are opt-in and stack on top.

| Layer | Purpose | Cost |
| --- | --- | --- |
| **Static Mode** (`StaticRuleContributor`) | Regex rules. Always on. | Zero |
| **LLM judge** (`LLMJudgeContributor`) | LLM semantic evidence. Opt-in via `--llm-augment`. | API call |
| **DeepSeek Lab** (`LabContributor`) | Hidden-state projection on DeepSeek-R1-Distill-Qwen-1.5B. Opt-in via `--lab-augment`. | Local GPU |
| **Black-box Eval** (independent) | Runs original / rewritten prompts on a target model and scores outputs. | API call |

Theoretical foundation:

- Anthropic — [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509)
- DeepSeek-AI — [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)

DeepSeek-first, not DeepSeek-only — see [DeepSeek roadmap](docs/DEEPSEEK_ROADMAP.md).

## Roadmap

- **v0.3** *(current)* — Skill HUD, MCP server, Lab activation projection on 4 axes
- **v0.3.1** — Remaining 4 axes; embedding contributor for offline fallback; VS Code / Cursor extension
- **v0.4** — MoE expert routing contributor on DeepSeek-MoE
- **v0.5** — Named steering vectors; output-time intervention API

Full plan: [project plan](docs/governance/PROJECT_PLAN.md), [open-source plan](docs/governance/OPEN_SOURCE_PLAN.md), [CHANGELOG](CHANGELOG.md).

## Documentation

- [Skill spec](docs/SKILL_ATTENTION_HUD.md) — attention HUD reference
- [MCP server](docs/MCP_SERVER.md) — Claude Code / Cursor / Cline / Continue setup
- [Architecture](docs/ARCHITECTURE.md) — hybrid evidence pipeline
- [FAQ](docs/FAQ.md) — common objections answered

<details>
<summary><b>More docs</b> — evidence model, governance, roadmaps, contributor guides</summary>

- [Evidence model](docs/EVIDENCE_MODEL.md) — three-layer evidence boundaries
- [DeepSeek roadmap](docs/DEEPSEEK_ROADMAP.md) — DeepSeek-first, not DeepSeek-only
- [Quality bar](docs/governance/QUALITY_BAR.md) — 10k-star reference benchmark
- [Operating rules](docs/governance/OPERATING_RULES.md) — visibility-first, engineering-grounded, five gates
- [Visibility plan](docs/governance/CONTRIBUTOR_VISIBILITY_PLAN.md) — 90-day contributor strategy
- [Open-source plan](docs/governance/OPEN_SOURCE_PLAN.md) — full launch plan
- [Project plan](docs/governance/PROJECT_PLAN.md) — north star and version roadmap
- [Publishing](docs/PUBLISHING.md) — release process
- [CHANGELOG](CHANGELOG.md) / [CITATION](CITATION.cff) / [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) / [CONTRIBUTING](CONTRIBUTING.md)

</details>

中文文档（含 China 镜像、PowerShell 编码 fix、完整命令样例）：[README.zh-CN.md](README.zh-CN.md)

## Contributing

Rule library quality = the project's core value. If you find a prompt pattern that isn't detected, a misfire, or want a new target preset — open an issue or PR.

Each rule contribution must include: pattern / affected axis / direction / weight / **mechanism** / **paper citation**. See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python scripts/acceptance_check.py
```

## License

MIT — see [LICENSE](LICENSE).

---

Built on Anthropic interpretability and DeepSeek-AI open research. This tool turns those findings into something agent hosts and prompt engineers can use every day, without having to actually answer the question of how the model "thinks" — just what it's about to focus on next.

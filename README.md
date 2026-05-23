# StateProbe

[![PyPI](https://img.shields.io/pypi/v/stateprobe.svg)](https://pypi.org/project/stateprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Erye932/stateprobe/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

> **The attention layer for LLM agents.**

Your agent already drifted — wrong focus, stale context, confidently editing files you never asked about. StateProbe catches it **before** the agent ships the answer. Works with **Claude Code**, **Cursor**, **Cline**, **Continue**, and any MCP host.

For closed-source agents, this is fast task-level attention inferred from text. Open-weight models unlock the optional Lab / future Runtime Probe path for activations and vectors.

English | [简体中文](https://github.com/Erye932/stateprobe/blob/main/README.zh-CN.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/Erye932/stateprobe/main/docs/images/skill_preview_demo.svg" alt="StateProbe catches stale context before an agent answers" width="900">
</p>

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

Copy-paste this after `pip install stateprobe` to catch a bad plan before it ships:

```bash
stateprobe skill preview \
  --context-text "Focus on safety; do not include deprecated APIs." \
  --plan-text "I will list deprecated APIs and explain why they are unsafe."
```

After the agent answers, audit alignment with user requirements:

```bash
stateprobe skill overlay \
  --context-text "Focus on safety; do not include deprecated APIs." \
  --output-text "The answer recommends a deprecated API first."
```

Or run the legacy prompt diagnostic, with the included
[`smart_but_not_answering`](https://github.com/Erye932/stateprobe/tree/main/demos/smart_but_not_answering) demo:

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

Full schemas: [Skill spec](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_ATTENTION_HUD.md), [MCP server](https://github.com/Erye932/stateprobe/blob/main/docs/MCP_SERVER.md).

## Two product lines

| Line | What | Status |
| --- | --- | --- |
| **Skill — Agent Attention HUD** | Shipped external control layer. Text-to-text task attention, preview before output, overlay after output, control levers for the next turn. Works with closed and open models. | ✅ Shipped |
| **Lab — Activation Projection** | Opt-in open-weight lab path. Projects prompt activations onto Persona Vectors on DeepSeek-R1-Distill-Qwen. Requires local model access. | ✅ Available / experimental |
| **Enterprise — Runtime Probe** | Future production line for hidden states, router traces, expert routing, output-state reports, and operator controls on open-weight models. | 🛠 Placeholder only |

**Boundary**: the Skill HUD never claims neural interpretability; it makes task-level attention visible and steerable from text. Closed-source APIs (OpenAI, Claude) cannot expose hidden states — OpenAI/Claude 物理上读不到 hidden states — so they run the Skill layer only. Open-source models (DeepSeek, Qwen, Llama) unlock the Lab path today and the future Runtime Probe line later.

## How it differs

|  | promptfoo | Guardrails AI | LangSmith | **StateProbe** |
| --- | --- | --- | --- | --- |
| Analyzes | Output quality | Output safety | Call traces | **Agent's planned attention before output** |
| When | After release | Runtime | Production | **Before each turn** |
| LLM API needed | Yes | Yes | Yes | **No (default)** |

Complementary, not competitive. promptfoo / Guardrails check what came out; StateProbe shapes what's about to come out.

## Architecture

Hybrid evidence pipeline ([ADR_009](https://github.com/Erye932/stateprobe/blob/main/docs/adr/009-hybrid-engine.md)): independent contributors emit confidence-weighted evidence, aggregated into 8 behavior axes. Static rules are always on (zero cost); the LLM and Lab layers are opt-in and stack on top.

| Layer | Purpose | Cost |
| --- | --- | --- |
| **Static Mode** (`StaticRuleContributor`) | Regex rules. Always on. | Zero |
| **LLM judge** (`LLMJudgeContributor`) | LLM semantic evidence. Opt-in via `--llm-augment`. | API call |
| **DeepSeek Lab** (`LabContributor`) | Hidden-state projection on DeepSeek-R1-Distill-Qwen-1.5B. Opt-in via `--lab-augment`. | Local GPU |
| **Black-box Eval** (independent) | Runs original / rewritten prompts on a target model and scores outputs. | API call |

Theoretical foundation:

- Anthropic — [Persona Vectors: Monitoring and Controlling Character Traits in Language Models](https://arxiv.org/abs/2507.21509)
- DeepSeek-AI — [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948)

DeepSeek-first, not DeepSeek-only — see [DeepSeek roadmap](https://github.com/Erye932/stateprobe/blob/main/docs/DEEPSEEK_ROADMAP.md).

## Roadmap

- **v0.3** *(current)* — Skill HUD, MCP server, Lab activation projection on 4 axes
- **v0.3.1** — Remaining 4 axes; embedding contributor for offline fallback; VS Code / Cursor extension
- **v0.4** — MoE expert routing contributor on DeepSeek-MoE
- **v0.5** — Named steering vectors; output-time intervention API

See [CHANGELOG](https://github.com/Erye932/stateprobe/blob/main/CHANGELOG.md) for the full version history.

## Documentation

- [Skill spec](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_ATTENTION_HUD.md) — attention HUD reference
- [MCP server](https://github.com/Erye932/stateprobe/blob/main/docs/MCP_SERVER.md) — Claude Code / Cursor / Cline / Continue setup
- [Architecture](https://github.com/Erye932/stateprobe/blob/main/docs/ARCHITECTURE.md) — hybrid evidence pipeline
- [FAQ](https://github.com/Erye932/stateprobe/blob/main/docs/FAQ.md) — common objections answered

<details>
<summary><b>More docs</b> — evidence model, ADRs, roadmaps, contributor guides</summary>

- [Evidence model](https://github.com/Erye932/stateprobe/blob/main/docs/EVIDENCE_MODEL.md) — three-layer evidence boundaries
- [DeepSeek roadmap](https://github.com/Erye932/stateprobe/blob/main/docs/DEEPSEEK_ROADMAP.md) — DeepSeek-first, not DeepSeek-only
- [Architecture decisions](https://github.com/Erye932/stateprobe/tree/main/docs/adr) — ADRs for hybrid pipeline and lab contributor
- [Publishing](https://github.com/Erye932/stateprobe/blob/main/docs/PUBLISHING.md) — release process
- [CHANGELOG](https://github.com/Erye932/stateprobe/blob/main/CHANGELOG.md) / [CITATION](https://github.com/Erye932/stateprobe/blob/main/CITATION.cff) / [CODE_OF_CONDUCT](https://github.com/Erye932/stateprobe/blob/main/CODE_OF_CONDUCT.md) / [CONTRIBUTING](https://github.com/Erye932/stateprobe/blob/main/CONTRIBUTING.md)

</details>

中文文档（含 China 镜像、PowerShell 编码 fix、完整命令样例）：[README.zh-CN.md](https://github.com/Erye932/stateprobe/blob/main/README.zh-CN.md)

## Contributing

Rule library quality = the project's core value. If you find a prompt pattern that isn't detected, a misfire, or want a new target preset — open an issue or PR.

Each rule contribution must include: pattern / affected axis / direction / weight / **mechanism** / **paper citation**. See [CONTRIBUTING.md](https://github.com/Erye932/stateprobe/blob/main/CONTRIBUTING.md).

```bash
python scripts/acceptance_check.py
```

## License

MIT — see [LICENSE](https://github.com/Erye932/stateprobe/blob/main/LICENSE).

---

Built on Anthropic interpretability and DeepSeek-AI open research. This tool turns those findings into something agent hosts and prompt engineers can use every day, without having to actually answer the question of how the model "thinks" — just what it's about to focus on next.

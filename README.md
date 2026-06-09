# StateProbe

[![PyPI](https://img.shields.io/pypi/v/stateprobe.svg)](https://pypi.org/project/stateprobe/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Erye932/stateprobe/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Tests](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml/badge.svg)](https://github.com/Erye932/stateprobe/actions/workflows/ci.yml)

> **A runtime state firewall for AI agents.**

AI agents are moving from chat to execution: writing code, calling tools, editing files, touching data, and shipping changes. The dangerous failures often start **before** the tool call: the agent has already locked onto the wrong task, followed stale context, become too agreeable, or entered an unreliable behavior state.

StateProbe is the control layer that catches that drift **before execution**. Today it ships as a local CLI / MCP preflight for agent workflows. The long-term line is deeper: activation vectors, emotion/persona vectors, and MoE routing signals for open-weight model runtime control.

Works with **Claude Code**, **Cursor**, **Cline**, **Continue**, and any MCP host.

English | [简体中文](https://github.com/Erye932/stateprobe/blob/main/README.zh-CN.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/Erye932/stateprobe/main/docs/images/skill_preview_demo.svg" alt="StateProbe catches stale context before an agent answers" width="900">
</p>

---

## Why

LLM observability mostly tells you what happened after the model answered or after the agent called tools. That is useful, but late. In production agent systems, the expensive failure is often earlier:

- The user asks for analysis; the agent starts editing files.
- The latest instruction pivots; the agent keeps following old context.
- The agent is about to call a tool while missing a hard constraint.
- A model upgrade changes sycophancy, confidence, or reasoning-budget behavior.

StateProbe gives the host a decision point before damage:

- **Detect** planned attention drift before the agent speaks or executes
- **Branch** into continue, warning, rewrite, boundary question, or context cut
- **Audit** the output afterwards and build a calibration trail
- **Extend** toward open-weight runtime probes when model internals are available

Runs **locally**. Costs **zero LLM tokens** by default. Plugs into any MCP host.

## Why not just ask the model to check itself?

Because self-reflection keeps the judge inside the same unstable system.

- A drifting model may not know it is drifting.
- A self-check is still text-level and can be contaminated by the same prompt/context.
- A second LLM judge adds latency, cost, and another nondeterministic dependency.
- Enterprise teams need a consistent control signal across agents, prompts, model versions, and deployments.

StateProbe's default layer is an external, deterministic preflight. For open-weight models, the long-term Runtime Probe line moves below text into hidden states, persona/emotion vectors, and MoE routing signals.

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

| Action | Meaning | Stops the agent? |
| --- | --- | --- |
| `continue` | Aligned. Agent can speak. | No |
| `continue_with_warning` | Risk signals exist, but evidence isn't strong enough for a hard stop. **Show the evidence; don't interrupt.** | No |
| `rewrite_planned_focus` | Plan misses user's actual must, with concrete evidence. **Don't ship.** Rewrite focus first. | Yes |
| `ask_boundary_question` | Visual / creative ambiguity. **Ask the user one yes/no first.** | Yes |
| `cut_context_contamination` | Agent is following stale context. **Cut the old direction first.** | Yes |

Every decision now ships with `confidence` (`low` / `medium` / `high`) and `evidence` — the concrete user requirements and gaps the decision was built on. **Destructive hard stops (`rewrite_planned_focus`, `cut_context_contamination`) only fire on `high` confidence.** `ask_boundary_question` can fire at `medium` because the cost is one user yes/no, not a rewrite. Everything weaker downgrades to `continue_with_warning` so StateProbe never destroys a workflow on a hunch. This is the contract that keeps the layer usable instead of a noisy referee.

`stateprobe skill overlay` returns an `interrupt_level` (`ok` / `watch` / `interrupt`) plus `attention_gaps` and `control_levers` for the next turn.

Full schemas: [Skill spec](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_ATTENTION_HUD.md), [MCP server](https://github.com/Erye932/stateprobe/blob/main/docs/MCP_SERVER.md).

## Current wedge, long-term control plane

StateProbe is deliberately staged:

| Stage | Status | What it proves |
| --- | --- | --- |
| **Open-source MCP / CLI** | Shipped | Agent drift can be caught before output/tool execution without another LLM call. |
| **Skill HUD** | Shipped | Hosts can branch on structured `activation_decision` instead of reading paragraphs of critique. |
| **Lab activation projection** | Experimental | Open-weight model activations can be projected onto behavior/persona axes. |
| **Team dashboard** | Planned | Teams need a record of drift cases, prompt versions, risk trends, and calibration decisions. |
| **Enterprise Runtime Probe** | Planned / placeholder | Open-weight model operators need hidden-state, router-trace, and output-state reports in production. |

The commercial shape is not "another prompt tool." The wedge is open-source developer adoption; the product is an agent runtime control plane for teams that run high-permission agents or open-weight models.

## What StateProbe is / is not

**StateProbe is** a runtime state firewall for agent workflows. It exposes — as structured control signals — what the agent is about to focus on, what it is about to ignore, and whether it is still attached to stale context, *before* the agent takes expensive actions (calls a tool, writes code, sends an email, renders an image).

**StateProbe is not**:

- **Not an oracle.** Rule-based judges have false positives and false negatives. That is why every verdict ships with `confidence` and `evidence`, and only `high` confidence ever stops an agent.
- **Not a replacement for human or LLM review.** Review agents look at finished output. StateProbe looks at planned focus. They are complementary, not substitutes.
- **Not a semantic correctness checker.** It does not know whether your code is right, whether your essay is true, or whether your design is good. It checks attention alignment, not domain truth.
- **Not a "spin up another agent to judge this one" wrapper.** The whole point is that the default path is local, deterministic, zero-API-cost, and emits a structured `activation_decision` your host can branch on — not a paragraph of LLM critique.
- **Not a finished enterprise control plane yet.** The shipped line is the Skill HUD. Runtime Probe, dashboard, access control, audit log, and deployment story are the next product line, not a claim of current production support.

The honest one-line pitch: **execution-time drift prevention today; open-weight runtime state control tomorrow**.

## Known failure modes

StateProbe will misjudge in these cases. The full list is in [`tests/fixtures/skill_cases.jsonl`](https://github.com/Erye932/stateprobe/blob/main/tests/fixtures/skill_cases.jsonl) (currently 19 documented `known_issue` cases out of 51 total). The recurring families:

- **Paraphrase / antonym blindness.** `must_not 提缺点` violated by `列举需要改进的地方` — no lexical overlap, no concept lexicon, false negative.
- **Avoidance-phrase false positive.** Plan `避免使用营销话术` literally contains the must_not keyword, so the matcher fires even though the intent is the opposite.
- **Implicit-realisation false positive.** A drawing plan that captures `放松` via `闭眼微笑、背景柔和` is hard-stopped because the abstract concept word is not literally present.
- **Modifier loss.** Plan covers the head must (`解释 RAG`) but loses a softer modifier (`面向新手`). Algorithm hard-stops; a human would warn.
- **Plan-substance gaps.** A plan that is just `好的` or just a clarifying question soft-warns instead of hard-stopping.

The fix path for each one is named in the fixture's `notes` field, not handwaved. None of them are blockers for the preflight contract; they are exactly the kinds of cases users will surface and grow the calibration suite around.

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
| Open-weight internals | No | No | No | **Planned Runtime Probe path** |

Complementary, not competitive. promptfoo / Guardrails check what came out; LangSmith-style tools show what happened; StateProbe tries to stop the wrong thing from happening in the first place.

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

- **v0.3** — Skill HUD, MCP server, Lab activation projection on 4 axes
- **v0.3.1** — Windows CLI encoding + launch demo polish
- **v0.4** *(current)* — Evidence-driven `activation_decision`: every verdict ships `confidence` + `evidence`, only `high` confidence hard-stops, plus a 51-case hand-labelled calibration suite (32 agree / 19 transparently documented known issues) and the contamination / `must_not` / modality-gate fixes that go with it
- **v0.4.x** — Close the documented known issues: antonym / paraphrase lexicon (ISSUE-005/006/020), modifier-aware coverage (ISSUE-001/009), plan-substance detection (ISSUE-012/018), more pivot markers (ISSUE-007); host feedback channel once user volume justifies it
- **v0.5** — MoE expert routing contributor on DeepSeek-MoE; named steering vectors; output-time intervention API

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

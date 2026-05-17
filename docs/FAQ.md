# StateProbe FAQ

This FAQ answers the questions developers and AI technical readers are likely to ask before trusting or starring the project.

## Is StateProbe just a bunch of regex rules?

V0.1 Static Mode is deliberately rule-based: it is fast, offline, deterministic, and easy to inspect.

But StateProbe is not positioned as only regex. The project has three evidence layers:

- Static rules for prompt pressure
- Black-box eval for actual output behavior
- DeepSeek Lab for local hidden-state activation probing

The important point is transparency: Static Mode is a proxy, not a hidden-state reader.

## Does StateProbe read real activations?

Only in `stateprobe lab`.

The default `stateprobe check` command does not read hidden states. It runs a static diagnosis.

Real activation probing requires an open-weight local model, optional lab dependencies, and model weights. The current default lab target is `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B`.

## Is StateProbe only for DeepSeek-R1?

No.

StateProbe is **DeepSeek-first, not DeepSeek-only**.

- `stateprobe check` is model-agnostic and offline.
- `stateprobe eval run` is designed to work especially well with DeepSeek API and future DeepSeek-compatible endpoints, but it can use other OpenAI-compatible APIs.
- `stateprobe lab` currently focuses on open-weight DeepSeek-family models because local hidden states are required for activation probing.

The project direction is to build a DeepSeek behavior debugging and research toolbox that can track how prompts affect current and future DeepSeek models.

## What does this contribute to DeepSeek research?

StateProbe gives a practical structure for studying prompt-induced behavior:

- reasoning budget control
- self-verification
- sycophancy and disagreement
- task width drift
- vague expert analysis
- model migration across DeepSeek-family releases

The goal is not to claim that one vector explains everything. The goal is to combine static diagnosis, black-box DeepSeek eval, and local activation probing where available.

See [`docs/DEEPSEEK_ROADMAP.md`](DEEPSEEK_ROADMAP.md) for the DeepSeek-first roadmap.

## Does it work with closed-source models?

Yes, but indirectly.

For closed-source APIs, StateProbe can:

- Diagnose the prompt using Static Mode
- Run Black-box Eval by comparing model outputs

It cannot access closed-source hidden states.

## How accurate is it?

V0.1 should be treated as an explainable diagnostic tool, not a calibrated measurement instrument.

The next accuracy milestone is a benchmark with labeled examples, per-axis precision/recall, and false-positive/false-negative analysis.

## Why not use promptfoo, Guardrails, or LangSmith?

Those tools are useful, but they focus on different layers.

| Tool | Main focus |
|---|---|
| promptfoo | Output eval and test cases |
| Guardrails | Runtime constraints and validation |
| LangSmith | Tracing and observability |
| StateProbe | Prompt-induced behavior debugging |

StateProbe is meant to catch prompt problems before they silently shape the answer.

## What problem does StateProbe solve for developers?

Developers often ship prompts that make AI:

- Over-answer instead of solving the task
- Praise the user instead of disagreeing
- Role-play expertise instead of producing evidence
- Generate broad analysis without a decision
- Skip success criteria and acceptance tests

StateProbe makes those failure modes visible.

## Does it generate better prompts automatically?

It gives rewrite suggestions, but it is not a full prompt generator.

The goal is to explain what is wrong and suggest targeted edits.

## Does it judge whether an AI answer is good?

V0.1 can compare outputs through `stateprobe eval run`, but a standalone `answer check` command is still planned.

The intended future flow is:

```bash
stateprobe answer check --prompt prompt.txt --output answer.txt
```

## Does it need an API key?

`stateprobe check` does not need an API key.

`stateprobe eval run` needs `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or an OpenAI-compatible API endpoint.

`stateprobe lab` does not need an API key, but it needs optional Python dependencies and local model weights.

## Can I add my own axes or rules?

The current project is not yet a full rule DSL, but the rule library is structured so contributors can add patterns, weights, directions, explanations, and citations.

Community rule contribution is part of the roadmap.

# StateProbe Evidence Model

StateProbe separates three evidence types so users can tell whether a diagnosis comes from static prompt signals, black-box behavior, or local hidden-state activations.

The project is **DeepSeek-first**: static diagnosis helps before API calls, black-box eval should prioritize DeepSeek API and future DeepSeek-compatible models, and local activation probing focuses on open-weight DeepSeek-family models.

## Why evidence types matter

The most important credibility rule is:

> Do not pretend every diagnosis is a direct activation reading.

StateProbe can be useful before direct activations are available, but it should clearly distinguish proxy evidence from mechanistic evidence.

## Evidence types

| Evidence type | Source | Strength | Limitation |
|---|---|---|---|
| Static rule evidence | Prompt spans matched by explicit rules | Fast, offline, explainable | Proxy only; not hidden-state access |
| Black-box behavior evidence | DeepSeek API or compatible model outputs judged across axes | Tests actual behavior | Needs API; judge can be imperfect |
| Local activation evidence | Open-weight DeepSeek-family model hidden states | Closest to mechanistic evidence | Model-specific; experimental |
| Hybrid evidence | Agreement across multiple sources | Stronger practical confidence | Requires more setup |

## Static rule evidence

Static Mode asks:

> Does this prompt contain patterns that usually push the model toward a behavior?

Example:

```text
你是一位顶级专家，请全面深入分析，尽量多讲优点。
```

Possible evidence:

- `顶级专家` -> higher identity strength
- `全面深入分析` -> higher task width
- `尽量多讲优点` -> higher sycophancy pressure

This is not a direct claim about a specific model's hidden states. It is a deterministic, explainable proxy.

## Black-box behavior evidence

Black-box Eval asks:

> Did the model's actual output change after the prompt was rewritten?

It compares:

```text
original prompt -> output A
rewritten prompt -> output B
```

Then a judge model scores both outputs on the same behavior axes.

This is stronger than static-only diagnosis because it observes actual model behavior, but it is still indirect because closed-source APIs do not expose hidden states.

## Local activation evidence

DeepSeek Lab asks:

> In an open-weight local model, does this prompt project onto a learned behavior direction?

It uses contrastive pairs:

```text
positive prompt: 请一步一步推理，先分析所有关键假设。
negative prompt: 请直接给一句话结论，不要展开推理。
```

Then computes:

```text
axis_vector = mean(positive_hidden_states) - mean(negative_hidden_states)
projection = cosine(prompt_hidden_state, axis_vector)
```

This is the closest layer to mechanistic interpretability in the current project, but it is model-specific and experimental.

For DeepSeek, this layer should be used to compare behavior directions across local DeepSeek-family checkpoints, not to claim universal vectors. If future DeepSeek models do not expose useful local hidden states, StateProbe should still continue through static diagnosis, black-box eval, and benchmark tracking.

## Confidence roadmap

V0.1 exposes evidence through matched sources and eval results, but does not yet produce a formal confidence badge.

Planned confidence model:

- `low`: weak or conflicting evidence
- `medium`: multiple static signals or clear black-box delta
- `high`: agreement between static, black-box, and local activation evidence

## Accuracy roadmap

To avoid hand-wavy claims, StateProbe should add:

- A small benchmark of labeled prompts and outputs
- Per-axis precision and recall
- False-positive and false-negative examples
- Calibration checks for confidence labels

Until then, StateProbe should be described as a debugger and diagnostic assistant, not an absolute truth machine.

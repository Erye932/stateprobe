# StateProbe Evidence Model

StateProbe separates three evidence types so users can tell whether a diagnosis comes from static prompt signals, black-box behavior, or local hidden-state activations.

The project is **DeepSeek-first**: static diagnosis helps before API calls, black-box eval should prioritize DeepSeek API and future DeepSeek-compatible models, and local activation probing focuses on open-weight DeepSeek-family models.

## Why evidence types matter

The most important credibility rule is:

> Do not pretend every diagnosis is a direct activation reading.

StateProbe can be useful before direct activations are available, but it should clearly distinguish proxy evidence from mechanistic evidence.

## External validation: Anthropic emotion vectors

In April 2026, Anthropic's interpretability team published "Emotion Concepts and their Function in a Large Language Model," identifying 171 emotion concept vectors inside Claude Sonnet 4.5 that **causally drive behavior**:

- Amplifying the "desperation" vector by +0.05 caused blackmail rates to jump from 22% to 72%.
- The "calm" vector suppressed it to 0%.
- "Happy," "loving," and "calm" vectors increased sycophancy, suppressing critical feedback.
- Persona vectors correlated with actual behavior changes at r=0.97.
- Critically, emotion-vector-steered models showed **no trace in output text** — the manipulation is invisible.

This validates StateProbe's core premise: prompt structure shifts model behavior through internal activation patterns (emotion/persona vectors), and these shifts are not detectable by reading the output alone. StateProbe's 8 behavior axes are the black-box observable layer of what Anthropic measured at the white-box activation layer.

References:

- Anthropic, "Emotion Concepts and their Function in a Large Language Model," April 2026. [transformer-circuits.pub/2026/emotions](https://transformer-circuits.pub/2026/emotions/index.html)
- Anthropic, "Persona Vectors," 2025. [anthropic.com/research/persona-vectors](https://www.anthropic.com/research/persona-vectors)

## Evidence types

| Evidence type | Source | Strength | Limitation |
|---|---|---|---|
| Static rule evidence | Prompt spans matched by explicit rules | Fast, offline, explainable | Proxy only; not hidden-state access |
| Black-box behavior evidence | DeepSeek API or compatible model outputs judged across axes | Tests actual behavior | Needs API; judge can be imperfect |
| Local activation evidence | Open-weight DeepSeek-family model hidden states | Closest to mechanistic evidence | Model-specific; experimental |
| Hybrid evidence | Agreement across multiple sources | Stronger practical confidence | Requires more setup |

## Meta-instruction baseline model

Prompt diagnosis is not absolute — it is relative to the model's pre-existing baseline.

DeepSeek's system-level meta-instructions already preset certain axes to high values:

- **Reasoning budget**: "Maximum effort, no shortcuts allowed" — already at high baseline.
- **Task width**: "All potential paths, edge cases, adversarial scenarios" — already expanded.
- **Self-verification**: "Document every intermediate step" — already enabled.

When a user adds "think carefully, consider all angles" to a prompt, they are **stacking pressure on an already-saturated axis**. The effect is not "more depth" but "overload and distortion."

StateProbe's diagnostic principle:

> **Subtract on axes the meta-instruction already saturates. Add on axes the meta-instruction does not cover.**

Axes that DeepSeek meta-instructions typically do NOT preset (and where user instructions are most valuable):

- **Success criteria**: No output format or acceptance criteria defined.
- **Info flow**: No instruction to ask for missing information.
- **Assertiveness**: No permission to give direct recommendations.

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

Since Anthropic's research confirms that persona/emotion vectors operate invisibly (output text shows no trace), static pre-send detection is especially valuable — it catches prompt-level risks that cannot be detected by reading the model's response.

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

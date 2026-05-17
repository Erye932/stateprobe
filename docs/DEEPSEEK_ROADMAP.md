# StateProbe DeepSeek Roadmap

StateProbe is DeepSeek-first, not DeepSeek-only.

The project should help developers and researchers understand how prompts shape DeepSeek-style reasoning behavior today, and provide reusable evaluation tools when future DeepSeek models appear.

## Why focus on DeepSeek

DeepSeek models are important because they make reasoning behavior visible at product scale:

- They are widely used through APIs.
- R1-style models made reasoning, reflection, and self-verification central to user expectations.
- Distilled open-weight variants allow local activation probing.
- Future DeepSeek models will likely change how reasoning budget, refusal, verification, and tool-use behavior appear in practice.

StateProbe should become a small but serious toolbox for tracking those behavior changes.

## DeepSeek-first layers

### 1. Prompt pressure diagnosis

`stateprobe check` does not require DeepSeek weights or API access.

It asks:

> Does this prompt push a DeepSeek-style reasoning model toward useful reasoning, or toward rambling, sycophancy, vague expertise, and unclear success criteria?

This layer is useful before spending API calls.

### 2. DeepSeek black-box behavior evaluation

`stateprobe eval run` compares real outputs from DeepSeek API or DeepSeek-compatible endpoints.

It should answer:

- Did the rewritten prompt make DeepSeek more direct?
- Did it reduce sycophancy?
- Did it preserve reasoning depth without causing overthinking?
- Did it improve self-verification?
- Did it produce decisions with acceptance criteria?

This is the practical layer for current closed/API models such as DeepSeek Chat or future DeepSeek Pro-style endpoints.

### 3. DeepSeek-family local activation probing

`stateprobe lab` is the research layer for open-weight DeepSeek-family models.

It should answer:

- Can we build a stable reasoning-budget direction?
- Can we build a self-verification direction?
- Are sycophancy and vague-expert behavior visible as directions?
- Which layers carry the strongest signal?
- Do directions transfer across DeepSeek-family checkpoints?

This layer must stay honest: it is experimental and model-specific.

## Research questions

StateProbe should focus on questions that matter for DeepSeek's future:

1. **Reasoning budget control**
   - When does a prompt request useful reasoning vs wasteful overthinking?
   - Can prompt edits preserve depth while reducing verbosity?

2. **Self-verification**
   - Which prompts reliably make DeepSeek check its own answer?
   - When does self-checking improve output quality, and when does it become performative?

3. **Sycophancy and disagreement**
   - Which prompt patterns make DeepSeek agree too easily?
   - Can prompts increase honest disagreement without making the model hostile?

4. **Task width drift**
   - When does DeepSeek turn a narrow task into broad analysis?
   - How can prompts keep scope tight without losing useful context?

5. **Future model migration**
   - When a new DeepSeek model appears, do the same prompt patterns still work?
   - Do old axis vectors still project meaningfully?
   - Which behaviors improve, regress, or merely change style?

## Vector boundary

Activation vectors are useful only under strict limits.

They can:

- Compare prompts inside one open-weight model.
- Explore layer-level behavior signals.
- Support hypotheses about prompt-induced behavior.
- Help compare DeepSeek-family checkpoints when metadata is controlled.

They cannot:

- Read closed DeepSeek API hidden states.
- Prove a universal behavior vector across all models.
- Replace black-box evaluation.
- Prove model intent.
- Guarantee future model compatibility.

If future models expose different internals or no useful vector interface, StateProbe should still continue through black-box behavior eval, prompt pressure diagnosis, and benchmark tracking.

## Near-term milestones

### V0.2: DeepSeek behavior benchmark

- Build 50-100 prompt pairs covering the 8 axes.
- Run DeepSeek API before/after rewrite.
- Store output behavior scores and failure cases.
- Publish a small calibration report.

### V0.3: DeepSeek Lab reproducibility

- Save and load axis vectors.
- Record model name, layer, tokenizer, prompt pairs, and device metadata.
- Add per-layer comparison reports.
- Add more DeepSeek-R1-Distill contrastive pairs.

### V0.4: DeepSeek model migration report

- Compare at least two DeepSeek-family models or checkpoints.
- Track which axes are stable and which drift.
- Publish a migration note for prompt engineers.

### V0.5: Agent and tool-use behavior

- Extend axes to agent prompts.
- Detect over-autonomy, unsafe tool-use pressure, and fake completion pressure.
- Evaluate DeepSeek-style models in tool-calling workflows.

## Success definition

StateProbe succeeds if it becomes a reproducible way to say:

> This prompt makes DeepSeek behave differently, here is the evidence layer, here is the failure mode, and here is how that behavior changed across model versions.

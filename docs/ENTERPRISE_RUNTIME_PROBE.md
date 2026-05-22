# StateProbe Enterprise: Runtime Probe

This document is a placeholder for the StateProbe enterprise line.

It is intentionally short. No enterprise code is implemented yet. This file exists so the direction is on the record and the directory structure is reserved.

## Two-line architecture

StateProbe has two product lines.

- **Skill line: Agent Attention HUD**
  - Already shipped in `stateprobe/skill/`.
  - Task-level attention, no model internals.
  - Suitable for any agent stack.
  - Documented in `docs/SKILL_ATTENTION_HUD.md`.

- **Enterprise line: Runtime Probe**
  - Not implemented yet.
  - Lives in `stateprobe/enterprise/` (placeholder only).
  - Target users are LLMOps and platform teams running open-weight models.

This document only covers the second line.

## What Runtime Probe is meant to do

Runtime Probe is the layer that looks at model internals during inference and reports state in production-friendly form.

Planned capabilities (none implemented yet):

- **Activation snapshots**: capture hidden states at chosen layers / spans during real inference.
- **Vector projections**: project activations onto persona vectors and behavior axes that already exist in `stateprobe/engines/lab.py`.
- **Logits and router traces**: for MoE-style open-weight models, expose top-k experts and routing distribution.
- **Output-state report**: per-response readout of behavior axes, drift from baseline, and risk flags.
- **Professional-attitude report**: aggregate signals about whether the model is staying in-role and meeting the operator's behavior contract.

Runtime Probe is intended to be open-weight first, with DeepSeek-family models as the first integration target.

## What Runtime Probe is NOT

Explicit non-goals for this line:

- It is not a prompt linter.
- It is not a prompt template tool.
- It is not a regex-based content checker.
- It is not a SOP generator.
- It is not a frontend toy.
- It does not replace the Skill line. The Skill line is the lightweight outer layer; Runtime Probe is the deep layer for teams that own the model.

## Relationship to existing code

The Lab layer in `stateprobe/engines/lab.py` already loads open-weight models and projects activations onto persona vectors. Runtime Probe will reuse and extend that foundation rather than start over.

Existing primitives that are likely to be reused:

- `LabContributor`
- `extract_activation`
- `load_model_and_tokenizer`
- persona vectors built by `scripts/build_lab_vectors.py`

What is missing for Runtime Probe and must be built later:

- a per-request runtime hook instead of a one-shot probe
- span-level and layer-level extraction instead of last-token only
- aggregation across many requests for trend reporting
- an output-state report format suitable for operators, not researchers
- access control, audit log, and deployment story

## Status

- Implementation: **none**
- API surface: **none**
- CLI surface: **none**
- Tests: **none**

`stateprobe/enterprise/` currently contains only a placeholder package that raises `NotImplementedError` if any consumer tries to use it. This is deliberate so accidental imports fail loudly instead of silently shipping a half-built layer.

## Boundary with the Skill line

To avoid drift, these two lines must not be mixed:

- The Skill line never claims neural interpretability.
- The Runtime Probe line never claims to work without model access.
- The Skill HUD must not be marketed as Runtime Probe output.
- Runtime Probe must not depend on Skill heuristics for its production claims.

This separation is the main reason both lines are documented as separate files instead of being merged into one roadmap.

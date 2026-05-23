# ADR-010: LabContributor — Persona Vectors as a third evidence layer

- **Status**: Proposed
- **Date**: 2026-05-18
- **Decision drivers**: project strategic blueprint §3.2 (move from lint to X-ray);
  blueprint §0 "10 月后是真护城河 vs lint 占位过渡品"; user request "make the project big and strong, get DeepSeek official recognition"

## Context

ADR_009 (v0.2) established the hybrid evidence pipeline where multiple
`EvidenceContributor` implementations emit `PollutionSource` and a single
aggregator merges them. v0.2 shipped two contributors:

- `StaticRuleContributor` — regex pattern matching, deterministic, fast, free
- `LLMJudgeContributor` — LLM semantic judging, opt-in, requires API

ADR_009 explicitly anticipated a third class of contributor at the time:

> LabContributor (v0.4, planned): hidden-state activation projection

This ADR formalizes that contributor's design and timing.

The motivation for shipping it sooner (v0.3 instead of waiting for v0.4) is
strategic: the project's value proposition long-term depends on actually
reading inside DeepSeek's models, not on text-level pattern matching. Every
month we delay the activation-reading layer is a month longer the project
looks like "yet another prompt linter built on top of regex + LLM-as-judge"
— a category that has zero defensible moat.

## Decision

Ship `LabContributor` in v0.3 using **Persona Vectors** (Anthropic 2025,
arXiv:2507.21509) on **DeepSeek-R1-Distill-Qwen-1.5B** (dense Qwen, not MoE)
as the third evidence layer in the hybrid pipeline.

## Why Persona Vectors specifically

Three other candidates considered for v0.3:

| Method | Sample needed | Train cost | Decision |
|---|---|---|---|
| **Persona Vectors** | 10-30 contrastive pairs | seconds (no training) | ✅ Chosen |
| Linear probe | 100-1000 labeled prompts | minutes | ❌ Labels not available |
| Sparse Autoencoder (SAE) | Full activation dataset | hours-days (own training run) | ❌ Out of compute budget |
| Sparse Linear Concepts (Goodfire) | Their hosted API | N/A | ❌ DeepSeek not on their roadmap |

Persona Vectors wins on:

1. **Tiny data requirement**: 4 axes × 3 contrastive pairs = 12 forward passes total to build all axis vectors.
2. **Zero training**: Anthropic's method is inference-time only.
3. **Cited credibility**: Public paper from a top lab; DeepSeek team is interpretability-aware and recognizes the technique.
4. **Already 90% scaffolded**: `stateprobe/lab/probe.py` was scaffolded in v0.1 and implements the algorithm; just needs end-to-end verification + integration.

## Why R1-Distill-Qwen-1.5B (and not larger)

| Model | Params | MoE | 8GB GPU? | Reason ruled in/out |
|---|---|---|---|---|
| R1-Distill-Qwen-1.5B | 1.5B | ❌ | ✅ FP16 ~3GB | ✅ Chosen — fits, real R1 lineage |
| R1-Distill-Qwen-7B | 7B | ❌ | 4-bit only (~5GB) | ⚠️ Possible but tight |
| DeepSeek-V2-Lite | 16B/2A | ✅ | ❌ ~10GB needed | ❌ V0.4 (cloud GPU) |
| DeepSeek-V2 / V3 / R1 | 200B+/37B+ | ✅ | ❌ Need 80GB+ | ❌ Out of scope |

1.5B is the smallest member of the R1 family, fits comfortably on the user's
existing 4060 Ti 8GB, and shares R1's reasoning fingerprint via distillation.
This is the realistic v0.3 target. MoE routing (the truly differentiating
feature) is deferred to v0.4 contingent on Phase 2 budget.

## Why 4 axes, not 8

The lab scaffold already defines `ContrastivePair` for 4 axes:
REASONING_BUDGET, SELF_VERIFICATION, TASK_WIDTH, SYCOPHANCY. These cover the
DeepSeek-R1 paper's central behavioral claims (deep reasoning, self-
verification) plus two universally applicable axes.

The remaining 4 (SUCCESS_CRITERIA, IDENTITY_STRENGTH, ASSERTIVENESS,
INFO_FLOW) are deferred to v0.3.1, driven by community feedback. Rationale:

- Blueprint §9.2: ship faster than perfect.
- 12 new contrastive pairs at v0.3.0 quality is ~3 days of focused design work.
- Community feedback often invalidates assumptions about which axes the lab
  layer should cover — let real usage drive the priority.

## Why opt-in (`--lab-augment`), not default

- GPU dependency would break installs for users without CUDA.
- Adds ~10-30s to first model-load. Default UX should stay fast.
- The blueprint's target user is SaaS AI engineers, most of whom do have
  GPUs but only when they explicitly need them.

`StaticRuleContributor` stays the always-on baseline. LLM and Lab layers are
both opt-in. This is consistent with v0.2 design where `--llm-augment` is
also opt-in.

## Why ship even if G3 (discrimination test) fails

The plan defines a hard gate at Day 4: if the lab projections agree with
static + LLM on every example, the lab layer adds no value and should not
ship as an evidence contributor.

**But the v0.3 release ships anyway**, with the lab component repositioned:

| G3 outcome | Lab role in v0.3.0 |
|---|---|
| ≥ 2 meaningful disagreements | ✅ Ships as full `LabContributor` evidence layer |
| < 2 disagreements (after 2 redesign attempts) | ✅ Ships as `stateprobe lab-probe` research subcommand only; not in hybrid pipeline |

The downgrade path is documented in `../archive/v0.3/TECHNICAL.md §8`. The reasoning: a
negative result on Persona Vectors at 1.5B is itself a contribution that
DeepSeek's interpretability team will find more honest than a fluffy
positive claim.

## Consequences

### Positive

- Activation reading is now actually shipped (not just a planned roadmap item).
- Project moves from "regex + LLM" category to "activation projection on DeepSeek family" category.
- Open-source reproduction of Persona Vectors on DeepSeek lineage models — the kind of artifact academic / interpretability community shares.
- Foundation for v0.4 MoE routing (same `EvidenceContributor` protocol, just new contributor).

### Negative

- Adds GPU dependency for opt-in feature (mitigated by `--lab-augment` being opt-in).
- Larger install size when `[lab]` extra is selected (~2.6GB torch + ~3GB model on first run).
- Adds Python 3.13 + CUDA wheel availability constraint (mitigated by Day 0 check + Python 3.12 fallback).
- Maintenance: HuggingFace transformers API changes occasionally; we now follow a major dependency.

### Neutral

- `EngineUnavailable` semantics extended: lab dependency failures (no GPU, no model) silently drop the contributor, consistent with LLM layer behavior.
- New optional file `lab_vectors/r1_distill_1.5b_v1.pt` — gitignored, generated locally per environment.

## Migration

No breaking changes vs v0.2.

| v0.2 | v0.3 | Action |
|---|---|---|
| `stateprobe check prompt.txt` | unchanged | none |
| `stateprobe check prompt.txt --llm-augment` | unchanged | none |
| (none) | `stateprobe check prompt.txt --lab-augment` | optional new flag |
| (none) | `stateprobe lab-probe "prompt text"` | optional new subcommand |
| `pip install stateprobe` | unchanged | none |
| (none) | `pip install stateprobe[lab]` | optional new extra |

## Alternatives considered (rejected)

1. **Defer lab entirely to v0.4** — rejected. Strategic blueprint §1.2 explicitly states lint is a stopgap; every release without activation reading delays the moat.
2. **Use a SaaS API for activation reading** (e.g., Goodfire) — rejected. They don't support DeepSeek; project differentiation is specifically DeepSeek depth.
3. **Add a `--lab-augment` flag but defer implementation** — rejected. A flag that doesn't work is technical debt.
4. **Train a linear probe from scratch on labeled data** — rejected. We don't have labeled activation data; collecting it takes longer than Persona Vectors. Reserved for v0.5+ if Persona Vectors hits a ceiling.

## References

- ADR-009: hybrid evidence pipeline
- Anthropic, Persona Vectors paper, arXiv:2507.21509
- Strategic blueprint §1.2, §3.2, §9.2 (offline document)
- `docs/archive/v0.3/TECHNICAL.md` — full technical detail
- `docs/archive/v0.3/EXECUTION.md` — day-by-day implementation plan
- `docs/archive/v0.3/ACCEPTANCE.md` — verification gates G0-G7

## Status changelog

- 2026-05-18: Proposed.

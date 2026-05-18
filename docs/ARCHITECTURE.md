# StateProbe Architecture

StateProbe is a DeepSeek-first layered debugger for prompt-induced LLM
behavior. Since v0.2 (ADR_009), diagnosis runs through a **hybrid evidence
pipeline**: multiple contributors (regex rules, LLM judge, future
embedding/lab) observe the same prompt and emit `PollutionSource` evidence;
a single aggregator merges and weights it by confidence into per-axis
readings. The rest of the pipeline (target compare, rewrite suggestions,
overlap detection, structural warnings, terminal/HTML rendering) is
contributor-agnostic.

## System overview

```text
prompt
  │
  ▼
┌─ Layer 1: structural detector  (always-on)
│  length / repetition / synonym stacking  → List[StructuralWarning]
└────────────────────────────────────────────────────────────────────
  │
  ▼
┌─ Layer 2: evidence contributors  (parallel, EvidenceContributor protocol)
│   • StaticRuleContributor (v0.1+, always-on, confidence=1.0)
│   • LLMJudgeContributor   (v0.2+, opt-in via --llm-augment)
│   • EmbeddingContributor  (v0.3, planned)
│   • LabContributor        (v0.4, planned, DeepSeek MoE expert routing)
│   ↓ merged pool
│   Dict[Axis, List[PollutionSource]]   (confidence per source)
└────────────────────────────────────────────────────────────────────
  │
  ▼
┌─ Layer 3: aggregator  (pure function, single source of truth)
│  • filter sources with confidence < MIN_AGGREGATE_CONFIDENCE
│  • per-axis: tanh(Σ direction × weight × confidence)
│  • anchor at model baseline                   → AxisReading per axis
└────────────────────────────────────────────────────────────────────
  │
  ▼
┌─ Layer 4: reasoner  (pure function)
│  • compute_deltas vs target preset
│  • suggest_rewrite (top-N)                    (rewriter.py)
│  • _detect_overlaps (meta-instruction baseline awareness)
└────────────────────────────────────────────────────────────────────
  │
  ▼
Report
  ├── terminal renderer  (cli.py)
  └── html_report.py
```

## Core modules

| Module | Responsibility |
|---|---|
| `stateprobe/models.py` | Shared dataclasses: axes, readings, targets, sources (with confidence), reports |
| `stateprobe/engines/base.py` | `EvidenceContributor` protocol; deprecated `Engine` alias |
| `stateprobe/engines/static.py` | `StaticRuleContributor` — regex layer |
| `stateprobe/engines/llm_judge.py` | `LLMJudgeContributor` — semantic layer with confidence gating |
| `stateprobe/rules.py` | Regex rule library used by `StaticRuleContributor` |
| `stateprobe/detector.py` | Orchestrates `diagnose()`: contributors → merged evidence → aggregator → reasoner |
| `stateprobe/rewriter.py` | Top-N rewrite suggestions from axis deltas |
| `stateprobe/structural.py` | Length / redundancy / synonym-stacking warnings independent of axes |
| `stateprobe/html_report.py` | Self-contained HTML reports |
| `stateprobe/cli.py` | User-facing CLI; `--llm-augment` for hybrid mode |
| `stateprobe/eval/` | Black-box **output** comparison via DeepSeek / OpenAI-compatible APIs |
| `stateprobe/lab/` | Experimental local hidden-state probing on DeepSeek open weights |

## Contributor layering

Each contributor emits evidence (`Dict[Axis, List[PollutionSource]]`); the
aggregator owns the only formula that combines evidence into a number.

| Contributor | Status | Needs | Strength | Limit |
|---|---|---|---|---|
| **StaticRuleContributor** | ✅ always-on | nothing | fast, free, fully explainable, deterministic | regex coverage is bounded by rule library |
| **LLMJudgeContributor** | ✅ v0.2 opt-in | `DEEPSEEK_API_KEY` (or any OpenAI-compatible endpoint) | semantic understanding; emits direction + strength + confidence + quoted span per axis | API cost + latency; quality bounded by judge model |
| **EmbeddingContributor** | 🔜 v0.3 | small local model (~120MB) | offline semantic fallback when API is unavailable | approximate; multilingual quality varies |
| **LabContributor** | 🔜 v0.4 | open-weight DeepSeek + GPU | true MoE expert-routing projection on residual stream | research scope; primarily for the X-ray product line |

Pipeline activation: `stateprobe check` runs static-only by default;
`stateprobe check --llm-augment` runs static + LLM in parallel and merges
their evidence. If the LLM contributor raises `EngineUnavailable`, the
detector silently drops it — static evidence still produces a report.

## Three execution modes

### Static Mode

Default command:

```bash
stateprobe check "你是资深专家，请全面分析这个项目"
```

Static Mode is deterministic and offline. It does not call an LLM. It estimates prompt pressure using explicit rules and reports matched spans as evidence.

### Black-box Eval

Optional command:

```bash
stateprobe eval run --original-file bad.txt --rewritten-file good.txt
```

Black-box Eval sends the original and rewritten prompts to a target model, then asks a judge model to compare output behavior across the same axes. The default route is DeepSeek-first, while still allowing OpenAI-compatible endpoints for comparison.

### DeepSeek Lab

Experimental command:

```bash
stateprobe lab probe "请一步一步推理，假设你是错的再修正" --axis reasoning_budget
```

DeepSeek Lab loads an open-weight DeepSeek-family model locally, extracts hidden states, builds contrastive axis vectors, and projects a new prompt onto those vectors.

## Data flow

### Static diagnosis

```text
prompt text
  -> rule matches
  -> PollutionSource[]
  -> AxisReading per axis
  -> AxisDelta against target preset
  -> RewriteSuggestion[]
  -> Report
```

### Black-box evaluation

```text
original prompt -> target model -> output A
rewritten prompt -> target model -> output B
output A + output B -> judge model -> AxisEvalScore[]
```

### Local activation probing

```text
positive/negative contrastive pairs
  -> hidden states
  -> axis_vector = mean(positive) - mean(negative)
  -> user prompt hidden state
  -> cosine projection
```

## Meta-instruction baseline awareness

StateProbe diagnoses prompt pressure **relative to the target model's meta-instruction baseline**, not in absolute terms.

DeepSeek's meta-instructions already preset certain axes (reasoning budget, task width, self-verification) to high values. A prompt instruction that duplicates an already-saturated axis causes overload, not improvement.

The diagnostic principle:

> Subtract on axes the meta-instruction already saturates. Add on axes the meta-instruction does not cover.

This means StateProbe's static warnings should indicate:

- Whether the detected pattern **overlaps** with a known meta-instruction preset (redundant pressure)
- Whether the prompt is **missing** instructions on axes that the meta-instruction does not cover (success criteria, info flow, assertiveness)

See [EVIDENCE_MODEL.md](EVIDENCE_MODEL.md) for the full baseline model and Anthropic's emotion vector validation.

## Design invariants

- `stateprobe check` must remain offline and cheap.
- Static Mode must not claim to read hidden states.
- Black-box Eval must be optional because it needs API keys.
- DeepSeek Lab must be optional because it needs heavy dependencies and model weights.
- Reports should show evidence, not just scores.
- Diagnostics should tell users what to **remove** (on saturated axes), not only what was detected.
- New axes or rules should include mechanism explanations and citations when possible.
- DeepSeek-specific experiments should record model name, layer, tokenizer, prompt pairs, and evaluation metadata.

## Current limitations

- V0.1 Static Mode is rule-based and should be treated as a proxy signal.
- DeepSeek Lab currently covers only a subset of axes with experimental contrastive pairs.
- There is not yet a public benchmark with calibrated accuracy numbers.
- Standalone `answer check` is planned but not implemented yet.

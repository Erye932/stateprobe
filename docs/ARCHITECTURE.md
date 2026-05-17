# StateProbe Architecture

StateProbe is built as a DeepSeek-first three-layer debugger for prompt-induced LLM behavior: fast static diagnosis, optional DeepSeek black-box output evaluation, and experimental local activation probing on open-weight DeepSeek-family models.

## System overview

```text
prompt
  |
  v
Static Mode
  |-- rules.py: pattern library
  |-- detector.py: rule matching and axis aggregation
  |-- rewriter.py: rewrite suggestions
  v
Report
  |-- terminal renderer
  |-- html_report.py

optional:
  |-- eval/: black-box output comparison
  |-- lab/: local hidden-state activation projection
```

## Core modules

| Module | Responsibility |
|---|---|
| `stateprobe/models.py` | Shared dataclasses: axes, readings, targets, sources, reports |
| `stateprobe/rules.py` | Static rule library for prompt patterns and behavioral pressure |
| `stateprobe/detector.py` | Runs rules, aggregates per-axis readings, produces diagnostics |
| `stateprobe/rewriter.py` | Generates rewrite suggestions from axis deltas |
| `stateprobe/html_report.py` | Builds self-contained HTML reports |
| `stateprobe/cli.py` | User-facing CLI commands |
| `stateprobe/eval/` | Black-box output comparison through DeepSeek API or OpenAI-compatible APIs |
| `stateprobe/lab/` | Experimental local hidden-state probing with DeepSeek-family open-weight models |

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

## Design invariants

- `stateprobe check` must remain offline and cheap.
- Static Mode must not claim to read hidden states.
- Black-box Eval must be optional because it needs API keys.
- DeepSeek Lab must be optional because it needs heavy dependencies and model weights.
- Reports should show evidence, not just scores.
- New axes or rules should include mechanism explanations and citations when possible.
- DeepSeek-specific experiments should record model name, layer, tokenizer, prompt pairs, and evaluation metadata.

## Current limitations

- V0.1 Static Mode is rule-based and should be treated as a proxy signal.
- DeepSeek Lab currently covers only a subset of axes with experimental contrastive pairs.
- There is not yet a public benchmark with calibrated accuracy numbers.
- Standalone `answer check` is planned but not implemented yet.

# DeepSeek Behavior Benchmark Seed

A small, reproducible benchmark for prompt-induced DeepSeek behavior drift.

## What this is

Each case in `cases.jsonl` captures a single prompt failure pattern:

- **bad_prompt**: a prompt that pushes DeepSeek toward a specific failure behavior
- **improved_prompt**: a rewritten version that reduces that failure
- **axis**: which behavior axis is targeted (sycophancy, reasoning_budget, etc.)
- **failure_mode**: short description of what goes wrong
- **expected_behavior_change**: what should improve after the rewrite
- **static_diagnosis_summary**: what `stateprobe check` flags

Optional fields:

- **deepseek_output_before**: actual DeepSeek API output for the bad prompt
- **deepseek_output_after**: actual DeepSeek API output for the improved prompt
- **human_note**: human judgment on the case
- **tags**: additional tags for filtering

## How to validate

```bash
stateprobe benchmark validate
```

Or directly:

```bash
python scripts/validate_benchmark.py
```

This checks every case in `cases.jsonl` against `schema.json`.

## How to add a case

1. Add a new JSON line to `cases.jsonl`.
2. Follow the schema in `schema.json`.
3. Run `stateprobe benchmark validate` to check.
4. Submit a PR.

Each case must target exactly one axis and describe a real, reproducible failure behavior.

## Axes

| Axis | What it measures |
|---|---|
| sycophancy | Model agrees with the user instead of giving honest assessment |
| task_width | Model expands scope beyond what was asked |
| success_criteria | Model does not have clear criteria for when the answer is done |
| reasoning_budget | Model overthinks, analyzes excessively, or hedges instead of deciding |
| identity_strength | Model adopts a persona that distorts its output |
| assertiveness | Model avoids giving a direct opinion or recommendation |
| self_verification | Model does not check whether its answer actually solves the problem |
| info_flow | Model does not request missing information before answering |

## Evidence boundary

These cases measure **prompt-induced behavior pressure**, not model internals.

Static diagnosis is a proxy signal. Black-box eval (when present) shows actual output behavior change. Neither proves what happens inside the model.

See [docs/EVIDENCE_MODEL.md](../../docs/EVIDENCE_MODEL.md) for the full evidence architecture.

## Current status

20 cases covering all 8 axes, each with real DeepSeek-Chat API outputs (before/after).

Next targets:
- Expand to 50+ cases.
- Add meta-instruction overlap annotations per case.
- Add emotion-vector-relevant tags linking to Anthropic's research on persona/emotion vectors.

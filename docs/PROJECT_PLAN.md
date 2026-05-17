# StateProbe Project Plan

StateProbe is a DeepSeek-first behavior debugger and research toolbox for prompt-induced LLM behavior.

This document is the unified project plan. It connects the product, research, engineering, benchmark, community, and visibility tracks into one execution roadmap.

The execution rule for every contributor and AI assistant working on this project is defined in [`OPERATING_RULES.md`](OPERATING_RULES.md): visibility-first, engineering-grounded.

## North star

StateProbe should become the open-source reference for this question:

> How do prompts change DeepSeek reasoning behavior, and how can we measure that reproducibly?

The project should help users say:

> This prompt makes DeepSeek behave differently. Here is the failure mode, here is the evidence layer, here is the reproduction path, and here is how that behavior changes across model versions.

## Positioning

### One-line positioning

> A DeepSeek-first debugger for prompts and LLM behavior.

### More precise positioning

StateProbe diagnoses prompt-induced behavior pressure across interpretable axes, then separates what the evidence can prove:

- static prompt-pressure signals
- black-box DeepSeek output behavior
- local activation probing on open-weight DeepSeek-family models

### What StateProbe is

- A prompt behavior debugger.
- A DeepSeek behavior benchmark seed.
- A research scaffold for local activation probing.
- A public collection of reproducible prompt failure cases.
- A toolchain for tracking behavior changes across future DeepSeek models.

### What StateProbe is not

- Not a universal prompt generator.
- Not a claim to read closed-model hidden states.
- Not a replacement for promptfoo, LangSmith, Guardrails, or full eval platforms.
- Not an activation-steering product.
- Not a claim that one vector explains every model.

## Target users

### Primary users

- Developers building DeepSeek-powered products.
- Prompt engineers debugging reasoning and output quality.
- Open-source users who want a runnable diagnostic tool.

### Secondary users

- AI reliability engineers.
- Interpretability readers.
- Researchers interested in behavior vectors and prompt-induced states.
- Contributors who want small, evidence-based open-source tasks.

## Core product loop

The product loop should be simple:

```text
bad prompt
  -> stateprobe check
  -> behavior-axis diagnosis
  -> rewrite suggestion
  -> DeepSeek black-box eval
  -> benchmark case or report
```

The research loop should be:

```text
contrastive prompt pair
  -> DeepSeek-family local model
  -> hidden-state extraction
  -> axis vector
  -> projection report
  -> compare with black-box behavior
```

## Evidence architecture

StateProbe has three evidence layers.

| Layer | Command | What it proves | What it cannot prove |
|---|---|---|---|
| Static diagnosis | `stateprobe check` | Prompt contains patterns likely to push behavior | It does not read hidden states |
| Black-box eval | `stateprobe eval run` | DeepSeek output behavior changed before/after rewrite | It does not expose internal mechanism |
| DeepSeek Lab | `stateprobe lab` | Local open-weight model activations project onto behavior directions | It is model-specific and experimental |

Every public claim should name the evidence layer.

## Behavior axes

StateProbe should continue to organize behavior around interpretable axes:

- sycophancy
- task width
- success criteria
- reasoning budget
- identity strength
- assertiveness
- self verification
- info flow

Future axes should only be added when there are enough prompt cases, rules, examples, and evidence notes.

## Version roadmap

### V0.1: Credible public MVP

Status: mostly complete.

Goal:

> A GitHub visitor understands the value, can run the demo, and trusts the evidence boundary.

Required outcomes:

- DeepSeek-first README.
- Runnable `stateprobe check` CLI.
- Demo 0: smart but not answering.
- Architecture, evidence model, FAQ, roadmap, quality bar, publishing docs.
- CI and repository governance files.
- Automatic acceptance check.

Exit criteria:

- `python scripts/acceptance_check.py` passes with 0 failures.
- GitHub repository is public and clean.
- README first screen is clear.
- No API keys or generated private artifacts are committed.

### V0.2: DeepSeek behavior benchmark seed

Goal:

> Move from a good idea to a reproducible public artifact.

Build:

- `benchmarks/deepseek_behavior_seed/cases.jsonl`
- `benchmarks/deepseek_behavior_seed/README.md`
- benchmark case schema
- benchmark validator
- 20 initial prompt pairs
- optional DeepSeek API output fields
- failure-case notes

Each case should include:

- case id
- axis
- failure mode
- bad prompt
- rewritten prompt
- expected behavior change
- static diagnosis summary
- optional DeepSeek output before
- optional DeepSeek output after
- human note

Exit criteria:

- At least 20 validated cases.
- Each of the 8 axes is represented.
- A contributor can add one case by editing one file and running one validator.
- README links to the benchmark seed.

### V0.3: Black-box DeepSeek eval reports

Goal:

> Show that StateProbe findings can be checked against real DeepSeek outputs.

Build:

- `stateprobe benchmark validate`
- `stateprobe benchmark run`
- JSON summary output
- Markdown or HTML benchmark report
- per-axis behavior delta summary
- failure examples where rewrite did not help

Exit criteria:

- Benchmark can run with `DEEPSEEK_API_KEY`.
- It also works in offline validation mode without an API key.
- Reports clearly separate static predictions from observed outputs.
- At least one public write-up uses the report.

### V0.4: DeepSeek Lab reproducibility

Goal:

> Make local activation probing reproducible, not just a demo.

Build:

- save/load axis vectors
- vector metadata format
- model name, layer, tokenizer, prompt pair, device metadata
- per-layer comparison report
- more contrastive pairs per axis
- design note explaining vector limits

Exit criteria:

- A user can reproduce an axis vector with the same model and layer.
- Reports include enough metadata to compare runs.
- Lab docs do not overstate what activation projections prove.

### V0.5: DeepSeek model migration reports

Goal:

> Make StateProbe useful when DeepSeek releases new models.

Build:

- migration benchmark runner
- model comparison report
- stable-vs-drifted axis summary
- prompt pattern compatibility notes

Exit criteria:

- At least two DeepSeek-family models or endpoints can be compared.
- The report says which prompt patterns still work and which drift.
- The project can publish a migration note when a new model appears.

### V1.0: Stable contributor-ready toolbox

Goal:

> A stable open-source project that developers and contributors can trust.

Build:

- stable CLI command groups
- documented benchmark format
- stable report format
- contributor workflow for benchmark cases
- release tags and changelog discipline
- enough examples for all major axes

Exit criteria:

- New contributors can submit benchmark cases without maintainer hand-holding.
- Public docs explain all commands and evidence limits.
- Project has at least one small release tag.
- The benchmark and reports are useful without reading source code.

## Workstreams

### 1. Product and CLI

Purpose:

> Make StateProbe useful in daily prompt debugging.

Next tasks:

- polish Demo 0 report preview
- add benchmark command group
- add confidence labels to static reports
- improve HTML report sections
- keep `stateprobe check` offline and fast

### 2. Benchmark and data

Purpose:

> Create the public artifact that makes the project citeable.

Next tasks:

- create 20-case DeepSeek seed benchmark
- define schema
- add validator
- document contribution format
- add false-positive and false-negative notes

### 3. DeepSeek eval

Purpose:

> Verify whether prompt rewrites change real DeepSeek output behavior.

Next tasks:

- benchmark runner using DeepSeek API
- output caching policy
- judge rubric documentation
- eval report generation
- examples with API redaction and safe publishing

### 4. DeepSeek Lab

Purpose:

> Explore local activation evidence for open-weight DeepSeek-family models.

Next tasks:

- vector persistence
- metadata recording
- layer comparison
- more contrastive pairs
- reproducibility notes

### 5. Documentation and trust

Purpose:

> Make claims precise and the project easy to understand.

Next tasks:

- keep README first screen sharp
- maintain evidence model discipline
- add failure case docs
- add benchmark contribution guide
- keep release checklist current

### 6. Community and visibility

Purpose:

> Help the maintainer become visible through useful, reproducible contributions.

Next tasks:

- publish one visible artifact per week
- create `good first issue` tasks
- write short technical posts
- respond to issues with evidence
- tag small releases

## First 30 days

### Week 1: Public clarity

- Ensure README, roadmap, visibility plan, and project plan are linked.
- Add Demo 0 HTML report preview or screenshot.
- Create first 5 GitHub issues.
- Publish short intro post.

### Week 2: Benchmark seed foundation

- Create benchmark folder and schema.
- Add 5 high-quality cases.
- Add validator.
- Document how to add a case.

### Week 3: Expand cases

- Grow to 20 cases.
- Cover all 8 axes.
- Add failure notes.
- Add static diagnosis snapshots.

### Week 4: First public benchmark note

- Run available DeepSeek black-box eval cases if API access is available.
- Publish a small calibration note.
- Tag a small release if the repo is stable.

## First public issues

Create these issues early:

1. Add 20-case DeepSeek behavior benchmark seed.
2. Add benchmark case schema and validator.
3. Add benchmark contribution guide.
4. Add Demo 0 HTML report preview.
5. Add case: expert persona causes vague analysis.
6. Add case: excessive reasoning budget causes overthinking.
7. Add case: sycophancy hides disagreement.
8. Add case: missing acceptance criteria causes unusable answers.
9. Add confidence labels to static reports.
10. Add DeepSeek Lab vector persistence design.

## Public writing plan

Publish short, evidence-bound posts:

1. "Why DeepSeek prompts often sound smart but miss the task"
2. "A small benchmark for DeepSeek prompt-induced behavior drift"
3. "Static rules vs black-box eval vs activation probing"
4. "How to reduce overthinking in DeepSeek prompts"
5. "How to test whether a DeepSeek prompt encourages self-verification"

Each post should include:

- one concrete prompt case
- one command to reproduce
- one screenshot or report
- evidence boundary
- link to a GitHub issue or benchmark case

## Non-goals until V0.3

Do not prioritize:

- web dashboard
- VS Code plugin
- account system
- marketplace integrations
- generic LLM platform positioning
- activation steering claims
- large-scale benchmark without a validated seed

## Quality gate

Every meaningful change must pass:

```bash
python scripts/acceptance_check.py
```

A change is not complete if it:

- breaks offline `stateprobe check`
- adds claims beyond the evidence model
- adds a feature without docs or demo path
- weakens DeepSeek-first positioning
- commits private data, API keys, generated reports, or model weights

## Success metrics

### Repository metrics

- README is understandable in 30 seconds.
- Demo runs in under two minutes.
- Acceptance check passes.
- Issues are small and contributor-friendly.
- Release notes are clear.

### Research metrics

- 20-50 benchmark cases exist.
- All 8 axes are represented.
- False positives and false negatives are documented.
- DeepSeek eval outputs are reproducible where API access exists.
- Lab runs include metadata.

### Visibility metrics

- three public posts exist
- one polished demo/report is easy to share
- contributors can add a benchmark case
- project is known for DeepSeek prompt behavior debugging, not generic AI tooling

## Decision rule

When choosing what to build next, prefer work that creates one of these:

1. A reproducible DeepSeek behavior case.
2. A benchmark artifact.
3. A clearer evidence boundary.
4. A contributor-friendly task.
5. A public report or write-up.

If a task does not support one of those, defer it.

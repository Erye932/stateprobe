# StateProbe Contributor Visibility Plan

This document explains how to turn StateProbe from a good repository into visible open-source contribution.

The goal is not to chase stars directly. The goal is to repeatedly publish small, credible, reproducible DeepSeek behavior findings that other developers can understand, run, and discuss.

## Positioning for visibility

StateProbe should be presented as:

> A DeepSeek-first behavior debugger and research toolbox for prompt-induced reasoning behavior.

The project should not compete by saying it is a bigger eval platform than promptfoo, LangSmith, or Guardrails. It should compete by being sharper:

- It focuses on prompt-induced behavior states.
- It separates static proxy evidence, black-box DeepSeek behavior, and local activation probing.
- It turns fuzzy prompt advice into reproducible diagnosis and reports.
- It builds a public trail of DeepSeek behavior cases over time.

## The contribution that can be seen

A visible open-source contribution needs at least one of these:

1. **A useful tool** people can run.
2. **A reproducible dataset or benchmark** people can cite.
3. **A technical finding** people can discuss.
4. **A clear framework** people can apply to their own work.

StateProbe already has the tool skeleton and framework. The missing part is repeated public evidence.

## 90-day strategy

### Phase 1: Make one undeniable demo

Time box: 1-2 weeks.

Goal:

> A visitor can run one command and immediately understand why StateProbe matters.

Deliverables:

- Improve Demo 0 into a polished DeepSeek-focused demo.
- Add a checked-in example report or screenshot.
- Add a short write-up: "DeepSeek looks smart but does not answer: a prompt behavior case study".
- Show before/after prompt, diagnosis, expected DeepSeek behavior difference, and evidence boundary.

Success signal:

- A developer can understand the project from one screenshot and one command.

### Phase 2: Publish a DeepSeek behavior benchmark seed

Time box: 2-4 weeks.

Goal:

> Create the first small public benchmark for prompt-induced DeepSeek behavior drift.

Deliverables:

- 20 prompt pairs before expanding to 50-100.
- Each pair has:
  - axis label
  - bad prompt
  - rewritten prompt
  - expected behavior change
  - static diagnosis
  - optional DeepSeek API output comparison
  - notes on failure cases
- A machine-readable format under `benchmarks/deepseek_behavior_seed/`.
- A benchmark README explaining how to reproduce results.

Success signal:

- Other people can add a new case through a PR.

### Phase 3: Turn findings into public writing

Time box: 4-8 weeks.

Goal:

> Make StateProbe discoverable outside GitHub.

Publish three short posts:

1. "Why DeepSeek prompts often sound smart but miss the task"
2. "A small benchmark for DeepSeek prompt-induced behavior drift"
3. "Static rules vs black-box eval vs local activation probing: what each can and cannot prove"

Each post should link to:

- The exact demo or benchmark case.
- The command to reproduce it.
- The evidence boundary.
- A GitHub issue inviting contributions.

Success signal:

- The project has something concrete to share on GitHub, X/Twitter, Hacker News, Reddit, Discord, or AI engineering communities.

### Phase 4: Build contributor paths

Time box: 6-12 weeks.

Goal:

> Make it easy for strangers to contribute without understanding the whole codebase.

Deliverables:

- GitHub labels:
  - `good first issue`
  - `demo case`
  - `benchmark case`
  - `rule improvement`
  - `DeepSeek eval`
  - `docs`
- Issue templates for benchmark cases and prompt failure cases.
- A `CONTRIBUTING.md` section explaining how to add one benchmark item.
- 5-10 pre-written issues with small scopes.

Success signal:

- A new contributor can make a meaningful PR in under one hour.

## What to build next

The next real feature should be the benchmark seed, not a plugin or web UI.

Recommended order:

1. `benchmarks/deepseek_behavior_seed/cases.jsonl`
2. `benchmarks/deepseek_behavior_seed/README.md`
3. `stateprobe benchmark validate`
4. `stateprobe benchmark run` using DeepSeek API when a key exists
5. A generated summary report

This creates a public artifact that is more valuable than another UI surface.

## Public narrative

Use this narrative when introducing the project:

> I am building StateProbe, a DeepSeek-first open-source debugger for prompt-induced behavior. It helps identify when a prompt pushes DeepSeek toward overthinking, sycophancy, vague expert analysis, or unclear success criteria. The project separates static prompt diagnosis, black-box DeepSeek output evaluation, and local activation probing on open-weight DeepSeek-family models.

Short version:

> StateProbe helps debug why a DeepSeek prompt sounds smart but does not actually answer.

## Weekly operating rhythm

Every week should produce one visible artifact:

- one demo case
- one benchmark case group
- one short technical note
- one issue for contributors
- one release note
- one screenshot/report improvement

Avoid invisible work for too long. Refactors are useful only when they unblock a visible artifact.

## What not to do yet

Avoid these until the benchmark seed and public case studies exist:

- VS Code plugin
- Web dashboard
- Large UI rewrite
- Claims about steering model internals
- Large-scale benchmark without a small validated seed
- Generic LLM platform positioning

## Recognition strategy

To be seen as an open-source contributor, focus on becoming associated with a specific, useful question:

> How do prompts change DeepSeek reasoning behavior, and how can we measure that reproducibly?

Do not try to be known for "AI tools" in general. Be known for this specific angle.

Good visibility comes from consistency:

- publish reproducible examples
- explain limitations honestly
- invite narrow contributions
- respond to issues with evidence
- release small versions often

## First 10 public issues to create

1. Add 20-case DeepSeek behavior benchmark seed.
2. Add benchmark case schema and validator.
3. Add README for reproducing DeepSeek black-box eval.
4. Add example HTML report preview for Demo 0.
5. Add failure case: expert persona causes vague analysis.
6. Add failure case: excessive reasoning budget causes overthinking.
7. Add failure case: sycophancy hides disagreement.
8. Add contribution guide for benchmark cases.
9. Add confidence labels to static diagnosis reports.
10. Add DeepSeek Lab vector persistence design doc.

## Success definition

After 90 days, StateProbe should have:

- a clear DeepSeek-first README
- one polished demo with report preview
- a 20-50 case DeepSeek behavior benchmark seed
- at least three public write-ups
- several good first issues
- one small release tag
- no overstated claims

If that happens, the project becomes more than a repository. It becomes a recognizable contribution area.

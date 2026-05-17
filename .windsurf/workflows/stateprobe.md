---
description: Advance StateProbe without drifting from the visibility-first, engineering-grounded strategy
---

# StateProbe execution workflow

Use this workflow whenever working on StateProbe strategy, documentation, benchmark design, CLI features, reports, demos, or release preparation.

## 1. Read the operating rule first

Open and follow:

- `docs/OPERATING_RULES.md`
- `docs/PROJECT_PLAN.md`
- `docs/CONTRIBUTOR_VISIBILITY_PLAN.md`

The non-negotiable rule is:

> Visibility-first, engineering-grounded.

## 2. Classify the requested work

Before implementing, classify the task into at least one category:

- public visibility
- developer usefulness
- reproducible benchmark evidence
- contributor readiness
- evidence discipline

If it fits none of those categories, explain why it should be deferred.

## 3. Apply the five gates

Ask whether the task improves:

1. visibility
2. usefulness
3. evidence
4. contribution
5. DeepSeek-first focus

A good task passes at least two gates.

## 4. Prefer visible artifacts

When choosing between options, prefer the one that produces a visible artifact:

- a runnable command
- a benchmark case
- a report or screenshot
- a public-facing README improvement
- a contributor-friendly issue or template
- a release note

Avoid long invisible refactors unless they unblock a visible artifact.

## 5. Protect evidence discipline

Do not claim StateProbe reads closed-model hidden states.

Do not present static rules as mechanistic proof.

Separate claims into:

- static prompt-pressure evidence
- black-box DeepSeek output behavior
- local activation evidence on open-weight DeepSeek-family models

## 6. Keep the next strategic target in view

The current highest-priority target is V0.2:

> DeepSeek behavior benchmark seed.

Prefer tasks that move toward:

- `benchmarks/deepseek_behavior_seed/cases.jsonl`
- `benchmarks/deepseek_behavior_seed/README.md`
- benchmark schema
- benchmark validator
- 20 high-quality prompt behavior cases
- contribution guide for adding cases

## 7. Run acceptance checks

After meaningful changes, run:

```powershell
python scripts/acceptance_check.py
```

The work is not complete if acceptance fails.

## 8. Summarize in project terms

When done, summarize:

- what became more visible
- what became more useful
- what evidence or benchmark path improved
- how contributors are helped
- what the next V0.2 step is

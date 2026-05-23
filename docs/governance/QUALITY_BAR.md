# StateProbe Quality Bar

StateProbe should be evaluated against the standard of a serious high-star open-source project, not merely a working local script.

## Principle

Every meaningful change should end with automatic acceptance checks.

The goal is not to say “it runs on my machine”. The goal is to make a new GitHub visitor feel:

> This project is clear, credible, useful, and maintained with taste.

## 10k-star reference bar

A strong open-source project usually has these qualities:

- **Instant clarity**: the first screen explains the pain and value in under 30 seconds.
- **Runnable demo**: a user can run one impressive demo quickly.
- **Evidence boundary**: claims are precise and do not overpromise.
- **Developer trust**: tests, docs, package metadata, and CLI help feel consistent.
- **Sharp differentiation**: users understand why this exists beside promptfoo, LangSmith, Guardrails, and eval tools.
- **Polished narrative**: the README tells a coherent story, not just a list of features.
- **Known limitations**: the project openly says what is proxy, what is black-box, and what is real activation probing.

## Acceptance levels

### Level 1: Local integrity

Required after every code or documentation change:

- Required docs exist.
- Demo files referenced by README exist.
- README links to architecture, evidence model, FAQ, and open-source plan.
- No obvious secret files are committed.
- Core CLI help works.
- Unit tests pass when the environment has test dependencies.

### Level 2: Open-source readiness

Required before GitHub launch:

- README first screen has a strong hook.
- Demo 0 shows a real pain: AI sounds smart but does not answer.
- Evidence model clearly separates static proxy, black-box behavior, and local activation.
- FAQ answers “is this just regex?” and “does it read activations?”.
- Placeholder repository URLs are replaced.
- Release checklist has no unresolved launch blockers.

### Level 3: High-star polish

Required before serious public promotion:

- One screenshot or HTML report preview exists.
- A benchmark or accuracy roadmap is visible.
- Repository governance files exist: contributing guide, changelog, security policy, code of conduct, citation file, CI, issue templates, and PR template.
- Failure cases are documented.
- **Contribution path**: contributors can find CI, issue templates, PR checklist, changelog, code of conduct, citation file, and contribution rules.
- The demo can be understood without reading source code.

## Default acceptance command

Run:

```bash
python scripts/acceptance_check.py
```

This command should be run at the end of each meaningful work session.

## What counts as failure

A change should not be called finished if:

- It adds a feature with no demo or docs.
- It changes positioning without updating README.
- It introduces claims that exceed the evidence model.
- It breaks CLI help or tests.
- It makes the project harder to understand for a new developer.

## Current project stance

StateProbe should present itself as:

> A debugger for prompts and LLM behavior.

It should not present itself as:

> A tool that can read every model's mind.

The stronger claim is not better. The more precise claim is more credible.

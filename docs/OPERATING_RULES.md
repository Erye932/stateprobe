# StateProbe Operating Rules

StateProbe should be run as a visibility-first, engineering-grounded open-source project.

The project must earn attention first, then keep that attention through useful developer experience, reproducible evidence, and contributor-friendly execution.

## The core rule

> Visibility-first, engineering-grounded.

This means StateProbe should optimize for being seen, understood, tried, and shared, but every visible artifact must be backed by runnable code, reproducible cases, clear evidence boundaries, or useful developer workflow.

The project should not choose between packaging and engineering. It needs both:

- packaging creates the first click
- demos create curiosity
- developer usefulness creates retention
- benchmark cases create credibility
- contributor paths create growth

## Why this rule exists

A technically correct project can still fail if nobody understands why it matters.

A well-packaged project can also fail if technical users try it and find no substance.

StateProbe should treat attention as the entry point and engineering quality as the retention mechanism.

## Mandatory AI execution rule

Any AI assistant helping with StateProbe must follow this rule before proposing or implementing work:

> Every task must improve at least one of: public visibility, developer usefulness, reproducible benchmark evidence, contributor readiness, or evidence discipline.

If a proposed task does not improve one of those, it should be deferred.

## The five gates

Before doing meaningful work, answer these five questions:

1. **Visibility**: Will this make the project easier to notice, understand, share, or demo?
2. **Usefulness**: Will this make a technical developer more willing to try or keep using the tool?
3. **Evidence**: Does this add reproducible data, clearer claims, or a stronger evidence boundary?
4. **Contribution**: Does this make it easier for outside contributors to help?
5. **Focus**: Does this keep the project DeepSeek-first and avoid generic AI-tool drift?

A task should pass at least two gates. If it only passes one, keep it small. If it passes none, do not do it.

## The traffic and trust loop

StateProbe should grow through a repeated loop:

```text
shareable prompt behavior case
  -> polished demo or report
  -> GitHub visit
  -> two-minute local run
  -> benchmark case contribution
  -> public write-up
  -> next case
```

This loop is more important than adding large features too early.

## What to prioritize

Prioritize work in this order:

1. polished demo and report preview
2. DeepSeek behavior benchmark seed
3. benchmark validation and contribution flow
4. real DeepSeek black-box output comparison
5. public technical write-ups
6. small release tags
7. local activation probing reproducibility

## What to avoid

Avoid work that creates activity without visibility or usefulness:

- adding more planning docs without producing cases, reports, or runnable improvements
- building a web app before the benchmark seed is useful
- adding a VS Code plugin before developers care about the CLI
- making broad claims about model internals
- generic LLM platform positioning
- large rewrites that do not create a public artifact
- features that require users to understand the whole codebase before getting value

## Packaging standard

Every public-facing feature should have:

- a clear name
- a one-sentence explanation
- a command or reproduction path
- a before/after example when possible
- an evidence boundary
- a screenshot, report, or output snippet when possible
- a contribution path if it can be extended by others

## Engineering standard

Every engineering change should preserve:

- offline `stateprobe check`
- passing tests and acceptance checks
- no committed API keys or private data
- clear separation between static, black-box, and activation evidence
- small, reviewable changes
- docs only when they support usage, evidence, release, or contribution

## Weekly operating rhythm

Each week should produce at least one visible artifact:

- one polished demo/report
- one benchmark case group
- one public technical note
- one contributor-friendly issue
- one release note
- one DeepSeek behavior comparison

Invisible work is allowed only when it unblocks a visible artifact.

## Decision rule

When there are multiple possible next steps, choose the one that most directly creates:

1. something developers want to try
2. something people can share
3. something contributors can extend
4. something that proves or limits a claim
5. something that strengthens the DeepSeek-first identity

## Current strategic bet

The near-term bet is not to become a large generic AI platform.

The near-term bet is:

> StateProbe becomes the most concrete open-source place to inspect, reproduce, and discuss DeepSeek prompt-induced behavior drift.

Everything else should support that bet.

## Hard refusals

Any AI assistant working on StateProbe must refuse to do the following, even if asked:

- fabricate DeepSeek API outputs or benchmark data
- post on social media on behalf of the user
- sign commits, articles, or posts with someone else's identity
- claim StateProbe reads closed-model hidden states
- claim activation vectors are universal across all models
- add commercial features, paywalls, or account systems
- change the project license without explicit user approval
- commit API keys, tokens, or credentials
- delete or weaken existing tests without explicit direction
- make claims beyond the evidence model

## Must-ask-user decisions

An AI assistant must stop and ask the user before:

- changing the project name or tagline
- changing the license
- writing public-facing copy (article, tweet, post) in the user's voice
- merging benchmark cases without user review
- changing the 90-day target or success criteria
- adding a new behavior axis without case evidence
- removing a document from the acceptance check

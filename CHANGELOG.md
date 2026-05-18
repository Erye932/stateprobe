# Changelog

All notable changes to StateProbe will be documented in this file.

## 0.2.0 - 2026-05-18 - Hybrid evidence engine

This release replaces the v0.2.0.dev0 either-or `--engine` model with a
**hybrid evidence pipeline** (ADR_009). Static rules are always-on; the LLM
judge is now an opt-in *additional layer* whose evidence merges with the
regex layer in the same per-axis pool. See `docs/ADR_009_hybrid_engine.md`
for the full rationale.

### Added

- **`EvidenceContributor`** protocol (`stateprobe.engines.base`): the new
  v0.2+ abstraction. A contributor observes a prompt and emits
  `Dict[Axis, List[PollutionSource]]`; the detector merges and aggregates.
- **`StaticRuleContributor`** (`stateprobe.engines.static`): the regex layer
  refactored as a contributor. Always-on, deterministic, `confidence=1.0`.
- **`LLMJudgeContributor`** (`stateprobe.engines.llm_judge`): the LLM
  semantic layer refactored as a contributor. Asks the judge for direction
  + strength + confidence + a quoted span per axis; observations below
  `MIN_LLM_CONFIDENCE` (0.30) are silently dropped so trivial prompts stay
  trivial.
- **`PollutionSource.confidence`** field: how sure the contributor is about
  the evidence. Default `1.0` for backward compat.
- **`stateprobe check --llm-augment`**: CLI flag enabling the hybrid mode
  (static + LLM merge). Replaces `--engine llm` (kept as deprecated alias).
- **`--llm-model` / `--llm-base-url`**: configure the LLM layer (renamed
  from `--judge-model` / `--judge-base-url`).
- **Confidence-gated aggregator**: `MIN_AGGREGATE_CONFIDENCE = 0.30`
  filters low-confidence sources before summing, keeping the trivial
  detection accurate across all contributor mixes.
- **`tests/test_engines.py`** rewritten (32 tests): covers contributor
  protocol conformance, parser format, confidence gating, hybrid merging,
  silent fallback when LLM unavailable, deprecated alias compatibility.

### Changed

- `diagnose()` signature: `engine=` is deprecated; new keyword-only args
  `llm_augment=` and `contributors=`. Default behavior unchanged
  (static-only).
- `detect_readings()` now accepts a `contributors` list; defaults to
  `[StaticRuleContributor()]` for backward compat.
- The detector lost its built-in regex matching code; it's now exclusively
  in `StaticRuleContributor`. Aggregation became a pure function
  (`_aggregate_to_readings`) shared by every contributor pipeline.

### Fixed

- **P0**: trivial prompts (`你好`, `?`, `   `) no longer get hallucinated
  rewrite suggestions when the LLM layer is on. The LLM judge now emits
  zero observations for empty/casual input; low-confidence ones are
  filtered out by the aggregator.
- **P1**: rewrite suggestions are capped at `MAX_SUGGESTIONS = 5` (down
  from an unbounded list that could produce 17+ items).
- **P1**: terminal alignment score is hidden on trivial reports — the
  number was misleading because it reflected baseline-vs-target, not
  user-driven pressure.
- **P1**: `tw_time_bounded` no longer false-positives on casual time
  mentions (`今天天气怎么样`); the rule now requires an adjacent
  scope/deadline marker. Regression covered in `tests/test_rules.py`.
- **P2**: `chat_completion` now masks API keys in `HTTPError` echo bodies
  via `_mask_secrets`. Bearer-shaped and `sk-…`-shaped tokens are also
  masked defensively.

### Deprecated (will be removed in v0.3)

- `Engine` protocol → use `EvidenceContributor`.
- `StaticEngine` / `LLMJudgeEngine` classes → use the contributor versions.
- `diagnose(engine=...)` → use `diagnose(llm_augment=...)`.
- `stateprobe check --engine llm` → use `--llm-augment`. The deprecated
  flag still works and emits a one-time CLI notice.

### Documentation

- `docs/ADR_009_hybrid_engine.md`: full architectural decision record.
- `docs/DEVELOPMENT.md`: contributor-facing development guide.
- `docs/RUNBOOK.md`: operations / release / platform-publishing SOP.
- `docs/v02_acceptance_review.md`: stress-test findings that drove this
  release.
- `docs/v02_stress_report.txt`: regenerated stress-test output (all
  assertions PASS).

## 0.1.0 - Unreleased

### Added

- Static prompt diagnosis across 8 behavior axes.
- Target presets for common prompt states.
- Terminal report with axis readings, pollution sources, and rewrite suggestions.
- Self-contained HTML report generation.
- Black-box eval scaffolding for comparing original and rewritten prompt outputs.
- DeepSeek Lab scaffolding for local hidden-state probing on open-weight models.
- Demo prompts for project decisions, code generation, teaching, and smart-but-not-answering cases.
- Architecture, evidence model, FAQ, quality bar, and open-source project plan docs.
- Automatic acceptance check for high-quality open-source readiness.
- DeepSeek behavior benchmark seed: 8 cases covering all 8 axes with schema, validator, and CLI integration (`stateprobe benchmark validate`).
- Decision log, public log, weekly review template.
- Hard refusals and must-ask-user rules in operating rules.

### Known limitations

- Static Mode is a proxy signal and does not read hidden states.
- Local activation probing is experimental and currently covers only a subset of axes.
- Public benchmark and calibrated accuracy metrics are not yet included.
- GitHub repository URLs are placeholders until the public repo exists.

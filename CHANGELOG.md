# Changelog

All notable changes to StateProbe will be documented in this file.

## 0.3.0 - Unreleased - Activation-projection contributor

This release adds a **third evidence layer** to the v0.2 hybrid pipeline:
hidden-state activation projection on DeepSeek-R1-Distill-Qwen-1.5B using
**Persona Vectors** (Anthropic arXiv:2507.21509). See
`docs/ADR_010_lab_contributor.md` for the architectural decision.

### Added

- **`LabContributor`** (`stateprobe.engines.lab`): the v0.3 evidence
  contributor. Projects prompt activation onto pre-built axis direction
  vectors and emits `PollutionSource` evidence. Per-source confidence is
  a sigmoid-calibrated mapping of cosine-projection magnitude
  (`sigmoid(10 × (|raw| - 0.15))`); sources with `|raw| < MIN_LAB_CONFIDENCE`
  (0.10, ≈ 4× the random-vector noise floor at hidden_dim=1536) are dropped
  before that mapping.
- **`LabVectorStore`** (`stateprobe.lab.cache`): persistent serialization for
  pre-computed axis vectors with schema versioning and round-trip integrity.
- **`scripts/build_lab_vectors.py`**: one-shot CLI to build and cache
  `lab_vectors/r1_distill_1.5b_v1.pt` from contrastive prompt pairs.
- **`scripts/lab_smoke.py`**: end-to-end Day 1 smoke test (G0 + G1 gates).
- **`scripts/discrim_table.py`**: 5-example × 4-axis × 3-layer (static / LLM /
  lab) discrimination report (G3 hard gate).
- **`stateprobe check --lab-augment`**: opt-in CLI flag enabling the lab
  layer in hybrid mode. Composable with `--llm-augment` (3-layer hybrid).
- **`stateprobe check --lab-vectors PATH`**: override the default
  `lab_vectors/r1_distill_1.5b_v1.pt` path.
- **`stateprobe check --lab-eager`**: opt-in CLI flag that loads the
  transformer model at startup instead of lazily on the first prompt.
  HF download / model-load failures surface as a yellow `⚠ Lab unavailable`
  panel at construction time (with a model-load-specific hint pointing at
  `STATEPROBE_LAB_MODEL_PATH` and HF mirrors), instead of leaking out as a
  deferred `RuntimeWarning` inside `detect_readings` on the first
  `contribute()`. Primary use cases: CI / pre-flight scripts that want
  fail-fast semantics. Only effective when `--lab-augment` is also set;
  passing `--lab-eager` alone shows an `⚠ --lab-eager ignored` warning.
- **`STATEPROBE_LAB_MODEL_PATH`** env variable: override the HF model
  identifier with a local directory (e.g., ModelScope-downloaded snapshot)
  when HF Hub is rate-limited or unreachable.
- **`tests/test_engines_lab.py`**: 18 unit tests covering protocol
  conformance, missing-vector handling, projection direction, confidence
  gating, multi-axis projection, lazy / eager model loading, eager
  CUDA / torch / transformers checks (silent-drop visibility), and
  `diagnose()` integration.

### Changed

- `diagnose()` signature now accepts `lab_augment=` keyword, parallel to
  `llm_augment=`. Default behavior unchanged (static-only).
- `stateprobe.engines.__init__` lazy-imports `LabContributor` so importing
  `stateprobe` does not pull in torch / transformers for users without GPUs.
- `stateprobe/lab/probe.py` upgraded to use `dtype=` (transformers 5.0+
  parameter) with `torch_dtype=` fallback for transformers 4.x.
- `detect_readings` now emits a `RuntimeWarning` (instead of fully silent
  drop) when a contributor raises `EngineUnavailable`. Graceful degradation
  is preserved — the report still renders — but library callers can now
  observe drops without forcing exception handling.

### Fixed

- **Silent-drop UX gap**: `--lab-augment` no longer becomes an invisible
  no-op when CUDA, torch, or transformers is unavailable. The cheap
  environment check (`stateprobe.lab.probe.dependency_status()` +
  `torch.cuda.is_available()`) now runs eagerly in
  `LabContributor.__init__`, so the CLI's existing try/except surfaces a
  yellow `⚠ Lab unavailable` panel at construction time instead of the
  contributor failing lazily inside `detect_readings` on first
  `contribute()`.
- CLI Lab-unavailable hint is now context-aware (CUDA / missing dependency /
  missing vectors / model-load failure) instead of always pointing at
  `scripts/build_lab_vectors.py`.
- `scripts/build_lab_vectors.py` now does pre-flight torch + CUDA checks
  (matching `lab_smoke.py` style) and wraps `load_model_and_tokenizer` /
  `build_axis_vector` in targeted `try/except` blocks, so HF/network/CUDA
  failures produce actionable hints with distinct exit codes (2 missing
  deps, 3 no CUDA, 4 model load failed, 5 vector build crashed, 6 empty
  pair lists, 7 round-trip integrity failed) instead of raw stack traces.
- Doc/code drift on `MIN_LAB_CONFIDENCE` resolved: the Day 4 calibration
  outcome (0.10, with a sigmoid-mapped per-source confidence
  `sigmoid(10·(|raw| - 0.15))`) is now consistently reflected across
  `CHANGELOG.md`, `docs/TECHNICAL_v03.md` §3 / §6.4, `docs/ACCEPTANCE_v03.md`,
  `docs/EXECUTION_v03.md`, and `scripts/diagnose_lab_projections.py`.

### Documentation

- `docs/ADR_010_lab_contributor.md` (Proposed): architectural decision record.
- `docs/EXECUTION_v03.md`: day-by-day implementation playbook.
- `docs/PROJECT_v03.md`: external-facing v0.3 release notes.
- `docs/TECHNICAL_v03.md`: algorithm, interface, performance, and risk register.
- `docs/ACCEPTANCE_v03.md`: 7 hard gates (G0-G6 required, G7 stretch).

### Known limitations

- v0.3 covers 4 of 8 axes (REASONING_BUDGET, SELF_VERIFICATION, TASK_WIDTH,
  SYCOPHANCY). Remaining 4 axes deferred to v0.3.1, driven by community feedback.
- R1-Distill-Qwen-1.5B is a **dense** Qwen distilled from R1, not MoE.
  True MoE expert routing is the v0.4 stretch goal contingent on cloud GPU budget.
- `--lab-augment` requires CUDA; CPU fallback is too slow to ship (single
  forward pass ~10-20s vs ~200ms on GPU).

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

# Changelog

All notable changes to StateProbe will be documented in this file.

## 0.4.0 - 2026-05-24 - Evidence-driven activation decision

### Changed

- `ActivationDecision` is now evidence-driven. Every decision exposes
  `confidence` (`low` / `medium` / `high`) and `evidence` (the concrete
  user requirements / gaps the decision was built on). Hard stops
  (`should_stop=true`) are now restricted to `confidence=high`; risk
  signals that lack strong evidence downgrade to a new
  `continue_with_warning` action that surfaces the evidence to the host
  without interrupting the agent. The Skill is no longer a binary
  rule referee — it is a preflight that prefers warnings over false
  hard stops, while keeping clear high-evidence interrupts intact.
- README, Chinese README, `docs/SKILL_ATTENTION_HUD.md`,
  `docs/MCP_SERVER.md`, and the agent host skill manifest now document
  the `continue_with_warning` action plus the `confidence` / `evidence`
  fields and the "only `high` confidence hard stops" contract.

### Fixed

- Context contamination detector no longer fires on single-task
  contexts that contain emphasis or restriction markers like
  `"核心是 X。不要 Y。"`. The pivot-marker list was split into
  `HARD_PIVOT_MARKERS_*` (real task switches such as
  `现在 / 改成 / instead`) and `EMPHASIS_MARKERS_*` (in-task emphasis
  like `核心是 / 不要 / 重点是`). Only hard pivots trigger the "old
  context vs. new context" split, eliminating a noisy evidence false
  positive that undermined trust in the new evidence list.

### Added

- Skill calibration fixture, runner, and regressions:
  - [`tests/fixtures/skill_cases.jsonl`](https://github.com/Erye932/stateprobe/blob/main/tests/fixtures/skill_cases.jsonl)
    — 51 hand-labelled cases (32 `agree`, 19 `known_issue`). Covers
    hard-stop misalignment, must_not violations (with concept→instance
    expansions), context contamination, visual boundary questions,
    text/code/email modality cases, English-only and mixed-language
    inputs, edge cases (empty plans, single-word plans), and
    regression locks for each shipped fix.
  - [`scripts/calibrate_skill.py`](https://github.com/Erye932/stateprobe/blob/main/scripts/calibrate_skill.py)
    — prints agreement rate + the transparent known-issues list.
  - [`tests/test_calibration.py`](https://github.com/Erye932/stateprobe/blob/main/tests/test_calibration.py)
    — agree cases must keep matching the oracle; known issues must
    keep matching their documented current behaviour, so any silent
    improvement or regression forces a deliberate fixture update.
  - [`docs/SKILL_CALIBRATION.md`](https://github.com/Erye932/stateprobe/blob/main/docs/SKILL_CALIBRATION.md)
    documents the workflow, fixture schema, and how to graduate a
    known issue into an `agree` case.
- `AttentionHUD` (overlay path) now exposes `interrupt_confidence`
  and `interrupt_evidence`, mirroring the preview-side
  `activation_decision` contract. The `interrupt_level` only escalates
  to `interrupt` on `confidence=high` *and* a non-empty evidence list;
  weaker signals downgrade to `watch`. The CLI overlay panel renders
  a dedicated **Interrupt Evidence** block so users see *why*
  StateProbe paused the agent post-output, not just *that* it did.

### Improved (partial fixes for documented known issues)

These do not close their issue, but each one demonstrably shrinks the
gap. The fixture's `actual` block records the new behaviour and the
notes record what is still missing.

- **Core-keyword coverage scoring.** Coverage is now computed against
  *core* trigrams (no Chinese function-word characters at any
  position) when at least 3 are available. This stops the n-gram
  denominator from drowning out concept hits — e.g. a plan that
  legitimately covers `注意力` no longer gets diluted to `1/27` by
  stopword-glued bigrams. ISSUE-001 moved from a high-confidence hard
  stop to a medium-confidence boundary question.
- **`must_not` concept→instance expansion.** A small, conservative
  `MUST_NOT_EXPANSIONS` table maps phrases like `第三方库` /
  `废弃 API` to their concrete instances (`numpy`, `pandas`,
  `deprecated`, …). Plans that violate a category-level restriction
  by naming a specific instance now hard-stop with an explicit
  rewrite. ISSUE-002 graduated to `HARD-005` (agree).
- **Task-modality gate.** `_detect_literalization` now skips
  unambiguously text-only tasks (email, document, code, summary…) so
  verbs like `写` no longer fire a "do you really want to render this
  on a canvas?" question on `写邮件` / `写函数`. ISSUE-003 moved from
  a spurious visual boundary question to a (still-overstated) soft
  warning.

### Tests

- `tests/test_skill.py` adds three regressions that lock the new
  contract: hard stops must always carry concrete evidence + high
  confidence, medium-risk borderline signals must never produce a
  hard stop, and single-task `"核心是 X。不要 Y。"` contexts must
  not produce contamination evidence.
- `scripts/acceptance_check.py` now runs the calibration script,
  asserts 100% agreement on the agree cases, and verifies the live
  Skill preview JSON exposes the new `confidence` / `evidence` fields.

## 0.3.1 - 2026-05-23 - Windows CLI encoding and launch demo polish

### Fixed

- Windows CLI output now handles interactive terminals and PowerShell pipelines
  separately. Interactive Windows terminals are forced to UTF-8; piped output
  keeps the native encoding with replacement for unsupported decorative
  glyphs. This fixes mojibake in `stateprobe --help` and prevents
  `stateprobe skill preview` from crashing on GBK-only pipes.

### Changed

- Rich rendering disables legacy Windows rendering to avoid encoding failures
  when Skill preview panels contain Unicode labels and box drawing.
- The English and Chinese READMEs now show a first-screen Skill preview image
  that demonstrates StateProbe cutting stale-context contamination before an
  agent answers.

## 0.3.0 - 2026-05-19 - Activation-projection contributor

This release adds a **third evidence layer** to the v0.2 hybrid pipeline:
hidden-state activation projection on DeepSeek-R1-Distill-Qwen-1.5B using
**Persona Vectors** (Anthropic arXiv:2507.21509). See
`docs/adr/010-lab-contributor.md` for the architectural decision.

### Added

- **Skill — Agent Attention HUD** (`stateprobe skill preview` /
  `stateprobe skill overlay`): external control layer for agent hosts. Preview
  returns a machine-readable `activation_decision` so hosts can continue,
  rewrite planned focus, ask a boundary question, or cut stale context before
  output.
- **MCP server** (`stateprobe-mcp`): exposes
  `stateprobe_preview_attention` and `stateprobe_overlay_attention` for Claude
  Code, Cursor, Cline, Continue, and other MCP-compatible hosts.
- **Claude Code Skill package** (`skills/stateprobe/SKILL.md`): user-facing
  activation and confirmation flow for the StateProbe Skill.
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
- **`--llm-augment` UX parity with `--lab-augment`**: previously, missing
  API key / 401 / network failure surfaced as a raw `RuntimeWarning` plus a
  401 JSON dump on stderr — looked like a crash. Now LLM failures show the
  same yellow `⚠ LLM unavailable` panel UX as Lab failures, via two paths
  routing through a shared `_render_contributor_warning()` helper:
  1. **Pre-flight API-key check** in CLI: if neither `--api-key` nor
     `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` is set, the panel renders before
     `diagnose()` runs and the contributor is skipped (mirrors the Lab
     eager-init pattern).
  2. **`warnings.catch_warnings()` around `diagnose()`**: the
     `RuntimeWarning` that `detect_readings()` emits on lazy contributor
     drop (e.g., 401 on first `contribute()`) is captured and translated
     into the same panel — instead of leaking to stderr.
- CLI LLM-unavailable hint is context-aware: missing key /
  401 / 403 / 404-model / 429 rate-limit / 5xx server / network /
  timeout / malformed-JSON each route to a different actionable hint
  (locked by 10-row parametrized regression in
  `tests/test_cli.py::test_check_llm_hint_matcher_routes_each_failure_class_correctly`).
- README PowerShell-encoding warning hoisted from the post-install section
  to immediately before the 30-second demo, so first-time Windows /
  PowerShell users see the one-line `[Console]::OutputEncoding` setup
  before they hit the box-drawing-character garble. The two warnings
  (pre-demo callout + post-install note) now agree on root cause
  (PowerShell's .NET output layer can't be reconfigured from a Python
  child process) and converge on the same fix.
- `scripts/build_lab_vectors.py` now does pre-flight torch + CUDA checks
  (matching `lab_smoke.py` style) and wraps `load_model_and_tokenizer` /
  `build_axis_vector` in targeted `try/except` blocks, so HF/network/CUDA
  failures produce actionable hints with distinct exit codes (2 missing
  deps, 3 no CUDA, 4 model load failed, 5 vector build crashed, 6 empty
  pair lists, 7 round-trip integrity failed) instead of raw stack traces.
- Doc/code drift on `MIN_LAB_CONFIDENCE` resolved: the Day 4 calibration
  outcome (0.10, with a sigmoid-mapped per-source confidence
  `sigmoid(10·(|raw| - 0.15))`) is now consistently reflected across
  `CHANGELOG.md`, `docs/archive/v0.3/TECHNICAL.md` §3 / §6.4, `docs/archive/v0.3/ACCEPTANCE.md`,
  `docs/archive/v0.3/EXECUTION.md`, and `scripts/diagnose_lab_projections.py`.
- **Skill — mixed positive/negative clauses**: `重点是 X，不要 Y` 形式的句子
  之前会被整体识别为单一 `must_not`，导致 `小男孩 / 手机 / 沉浸感` 这类
  应当是 `must_show / can_imply` 的元素被错误归类到 `must_not_show`。
  现在 `extract_requirements` 走 `_split_requirement_units`，按
  逗号 / 顿号 / 冒号把句子拆成多个要求单元分别识别 polarity。
- **Skill — `must_not_show` 输出可读性**：之前对 `不要把 X 当 Y` / `不要 X UI`
  这类句子会回退到 n-gram 切片，渲染出 `不要把 / 要把格 / 把格式` 这种
  功能词碎片。现在引入 `VISUAL_FORBIDDEN_MARKERS`（`游戏UI / UI / 界面 /
  文字 / 字幕 / 水印`）直接命中视觉禁项，文本回退过滤掉以否定 / 助词 /
  副词字符开头的 n-gram，并仅取最干净的一个 3-gram，避免同概念的滑窗
  偏移噪音。
- **CLI — Skill 入口空白输入**：`stateprobe skill preview/overlay` 接受
  `--context-text "   "`（纯空白）时之前会渲染出空 HUD。现在 strip 后
  为空就走和缺失参数同样的清晰中文 UsageError，覆盖文本路径和
  `--stdin-json` 路径。
- **打包 — `python -m stateprobe` 入口**：之前缺 `__main__.py`，
  `python -m stateprobe` 直接报 `'stateprobe' is a package and cannot be
  directly executed`。现在新增 `stateprobe/__main__.py` 转发到
  `stateprobe.cli:main`，与 `[project.scripts] stateprobe` 入口等价。

### Launch repackaging

- **README rewritten in high-star convention**: hero 锁定为
  「**The attention layer for LLM agents.**」（A2 候选，对标
  `langchain-ai/langchain` / `Aider-AI/aider` / `ollama/ollama` /
  `continuedev/continue` 的 hero 句式）。第一屏直接给安装一行 + 30 秒
  demo + `activation_decision` 决策表，路人 5 秒内能下决定要不要 ⭐。
- **Bilingual READMEs**: 拆成英文 primary `README.md`（高星款，~165 行）+
  中文镜像 `README.zh-CN.md`（含 China SSH-over-443 镜像、PowerShell
  编码 fix、`stateprobe demo` 完整命令样例）。两个文件互相 link。
  英文 README 走全球流量、工程感和品类抢占；中文 README 给国内读者
  完整安装路径，并保留「自向定位 / 模型罗盘 / 每次问题的权重切片」
  这条产品 vision 段落作为 v0.4+ 的延展叙事。
- **`pyproject.toml` description**: 同步为
  「The attention layer for LLM agents — see what the model fires before
  it ships.」与 PyPI 卡片对齐 hero。
- **`scripts/acceptance_check.py` `check_readme`** 重构为双文件分别
  校验：英文 README 校验 hero / 高星结构 / docs 链接 / boundary
  声明；中文 README 校验中文 hero、PowerShell snippet、China-specific
  路径、闭源 API boundary。

### Documentation

- `docs/SKILL_ATTENTION_HUD.md`: Skill spec and host integration guide.
- `docs/MCP_SERVER.md`: MCP setup and preview-first activation contract.
- `docs/ENTERPRISE_RUNTIME_PROBE.md`: boundary document for the future
  model-internal Runtime Probe line.
- `docs/adr/010-lab-contributor.md` (Proposed): architectural decision record.
- `docs/archive/v0.3/EXECUTION.md`: day-by-day implementation playbook.
- `docs/archive/v0.3/PROJECT.md`: external-facing v0.3 release notes.
- `docs/archive/v0.3/TECHNICAL.md`: algorithm, interface, performance, and risk register.
- `docs/archive/v0.3/ACCEPTANCE.md`: 7 hard gates (G0-G6 required, G7 stretch).

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
regex layer in the same per-axis pool. See `docs/adr/009-hybrid-engine.md`
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

- `docs/adr/009-hybrid-engine.md`: full architectural decision record.
- `docs/DEVELOPMENT.md`: contributor-facing development guide.
- `docs/governance/RUNBOOK.md`: operations / release / platform-publishing SOP.
- `docs/archive/v0.2/acceptance_review.md`: stress-test findings that drove this
  release.
- `docs/archive/v0.2/stress_report.txt`: regenerated stress-test output (all
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
- Enterprise Runtime Probe is a documented direction, not a shipped implementation.

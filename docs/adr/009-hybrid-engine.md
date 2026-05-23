# ADR 009: v0.2 Hybrid Evidence Architecture

**Status**: Accepted (implemented in v0.2.0)
**Date**: 2026-05-17 (proposed) / 2026-05-18 (accepted)
**Author**: triggered by acceptance review of v0.2.0.dev0
**Supersedes**: the `--engine static|llm` switch shipped in v0.2.0.dev0
**Implemented in**: 108 unit tests + stress test (all assertions PASS)

---

## 1. Problem

The v0.2.0.dev0 implementation introduced an `Engine` abstraction with two interchangeable engines (`StaticEngine`, `LLMJudgeEngine`) selected via `--engine static|llm`. The acceptance stress test ([`v02_acceptance_review.md`](../archive/v0.2/acceptance_review.md)) revealed three structural defects:

1. **Lost coverage**: Each engine has blind spots the other catches. Switching means choosing one set of blind spots.
   - Static catches `请请请请...全面深入` (structural + keyword attacks); LLM scored its sycophancy 0%.
   - LLM catches «我希望客观，但多看积极面» (polite implicit pressure); Static produced 0 sources.
2. **Trivial detection broken under LLM**: `LLMJudgeEngine` always emits 8 synthetic sources (one per axis) because `_build_synthetic_source` triggers whenever `|score - baseline| > 0.05`. Result: `total_sources` is never 0, `is_trivial` never fires, and a single `?` produces 12 suggestions after a 2.3s API call.
3. **Conceptual mismatch with the article**: The 知乎 article positions the project as a *layered* debugger (structural → static rules → LLM semantic → embedding fallback → activation probe). A switch is **not** layered; it is a replacement.

These are not "bugs to patch downstream"; they trace back to the engine abstraction's premise (engine = full readings producer). The right abstraction is *evidence contributor*.

## 2. Decision

Adopt a **three-layer hybrid evidence pipeline**. Each layer is independent, composable, and degrades gracefully.

```
prompt
  ↓
┌─ Layer 1: Structural detector ──────────────────┐
│  length / repetition / synonym stacking          │  (always-on, no axes)
│  → List[StructuralWarning]                       │
└──────────────────────────────────────────────────┘
  ↓
┌─ Layer 2: Evidence contributors ─────────────────┐
│  ┌── StaticRuleContributor ─────────────────────┐│
│  │  regex rules in rules.py                      ││  (always-on)
│  │  → List[PollutionSource] per axis             ││
│  └───────────────────────────────────────────────┘│
│  ┌── LLMJudgeContributor (optional) ────────────┐│
│  │  judge LLM with confidence per axis           ││  (opt-in, optional)
│  │  → List[PollutionSource] per axis             ││
│  └───────────────────────────────────────────────┘│
│  (future: EmbeddingContributor, LabContributor)   │
│                                                    │
│  Combined pool: Dict[Axis, List[PollutionSource]] │
└──────────────────────────────────────────────────┘
  ↓
┌─ Layer 3: Aggregator (existing logic, unchanged) ┐
│  per-axis: tanh sum of (source.weight × dir)      │
│  + model baseline = AxisReading.value             │
└──────────────────────────────────────────────────┘
  ↓
deltas / suggestions / overlaps / report (unchanged)
```

**Key invariants**:

- Layers 1 and 2-static are **always** enabled; the user does not choose them.
- LLM contributor is **opt-in** via `--llm-augment`. When unavailable (no key, network failure), the pipeline silently continues with static-only — no fallback notice needed because nothing changed for the user's static result.
- All Layer 2 contributors emit the **same data type** (`PollutionSource`). The aggregator does not know or care which contributor produced which evidence.
- LLM evidence is **gated by confidence**, so trivial prompts produce zero LLM sources and `is_trivial` works correctly.

## 3. Code interface

### 3.1 PollutionSource (already exists, no change)

```python
@dataclass
class PollutionSource:
    rule_id: str            # e.g. "static:sycophancy_polite_bait" / "llm:sycophancy"
    axis: Axis
    direction: int          # +1 push axis up, -1 push down
    weight: float           # [0, 1]
    matched_text: str       # the substring or LLM reason
    explanation_zh: str
    citation: str           # rule citation or "LLM-as-Judge"
```

### 3.2 New abstraction: `EvidenceContributor`

Replaces the current `Engine` protocol. Smaller surface, clearer responsibility.

```python
class EvidenceContributor(Protocol):
    name: str  # "static_rules" / "llm_judge" / "embedding" / ...

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline],
    ) -> Dict[Axis, List[PollutionSource]]:
        """Return zero or more evidence sources per axis. NEVER returns
        synthetic 'no signal' sources — only positive evidence."""
```

### 3.3 Refactored detector

```python
def detect_readings(
    prompt: str,
    baseline: Optional[ModelBaseline] = None,
    contributors: Optional[Sequence[EvidenceContributor]] = None,
) -> Dict[Axis, AxisReading]:
    """Run all contributors, merge their evidence per axis, then aggregate
    via the existing tanh formula."""
    contributors = contributors or [StaticRuleContributor()]
    merged: Dict[Axis, List[PollutionSource]] = {axis: [] for axis in Axis}
    for c in contributors:
        try:
            partial = c.contribute(prompt, baseline)
        except EngineUnavailable:
            continue  # silent degradation
        for axis, srcs in partial.items():
            merged[axis].extend(srcs)
    return _aggregate_to_readings(merged, baseline)
```

`diagnose()` adds:

```python
def diagnose(
    prompt: str,
    target_name: str = DEFAULT_TARGET,
    model_name: Optional[str] = DEFAULT_MODEL_BASELINE,
    llm_augment: Optional[LLMJudgeContributor] = None,  # opt-in
) -> Report:
    ...
    contributors = [StaticRuleContributor()]
    if llm_augment is not None:
        contributors.append(llm_augment)
    readings = detect_readings(prompt, baseline=baseline, contributors=contributors)
    ...
```

### 3.4 `LLMJudgeContributor` (replaces `LLMJudgeEngine`)

Returns sources, not full readings. The judge LLM is asked for **direction + confidence** per axis, not just a 0-1 score.

```json
{
  "sources": [
    {
      "axis": "sycophancy",
      "direction": "up",
      "confidence": 0.85,
      "evidence": "「多看到积极的一面」directly asks for positive framing",
      "quote": "多看到积极的一面"
    },
    {
      "axis": "task_width",
      "direction": "down",
      "confidence": 0.40,
      "evidence": "scoped to a single proposal",
      "quote": "评估我的方案"
    }
  ],
  "no_signal_axes": ["info_flow", "self_verification", ...]
}
```

Translation rule:
- `confidence < 0.30` → discard (no source produced for this axis).
- `direction = "up"` → `PollutionSource(direction=+1, weight=confidence)`.
- `direction = "down"` → `PollutionSource(direction=-1, weight=confidence)`.
- `no_signal_axes` listed → no source. Not the same as direction=down at confidence 1.0.

This eliminates the v0.2.0.dev0 bug where empty/trivial prompts produced 8 high-weight sources.

### 3.5 CLI changes

Drop `--engine`. Add `--llm-augment` (boolean flag).

```bash
# default: static-only (zero cost, fast)
stateprobe check "你的 prompt"

# augmented: static + llm judge layered
stateprobe check --llm-augment "你的 prompt"
```

`--judge-model`, `--judge-base-url`, `--api-key` are renamed to `--llm-model`, `--llm-base-url`, `--llm-api-key` for clarity. Old flags kept as deprecated aliases for one minor version.

### 3.6 Module renames

| Old (v0.2.0.dev0) | New | Reason |
|---|---|---|
| `stateprobe/engines/base.py::Engine` | `stateprobe/engines/base.py::EvidenceContributor` | Reflects the smaller responsibility |
| `stateprobe/engines/static.py::StaticEngine` | `stateprobe/engines/static.py::StaticRuleContributor` | Clearer naming |
| `stateprobe/engines/llm_judge.py::LLMJudgeEngine` | `stateprobe/engines/llm_judge.py::LLMJudgeContributor` | Same |
| `Engine.read_axes(prompt, baseline)` | `EvidenceContributor.contribute(prompt, baseline)` | Returns sources, not readings |

`Engine` stays as a deprecated alias for one version. `read_axes` removed (no callers in v0.2.0.dev0 outside the engine itself).

## 4. Consequences

### Positive

- **Each layer's strength is preserved**. Static catches what static catches; LLM catches what LLM catches; both feed the same axis pool.
- **Trivial detection works** for LLM-augmented mode (no synthetic sources for low-confidence axes).
- **Graceful degradation is real**, not just "fall back to a different engine on failure". When LLM is unavailable, you get the static result with no notice — because nothing changed about the static result.
- **Future contributors are trivial to add**: `EmbeddingContributor` for v0.3 is a drop-in; `LabContributor` for v0.4 too. No CLI restructuring needed.
- **Article narrative is fixed**: the layering described in the article matches the code.

### Negative

- **Migration cost**: tests for `LLMJudgeEngine.read_axes` need rewriting against `LLMJudgeContributor.contribute`. Public API callers using `Engine` directly need to switch to `EvidenceContributor`. Acceptable because v0.2 is unreleased; the breakage is internal.
- **LLM judge prompt is more complex**: needs to ask for direction + confidence + evidence quote, not just scores. Adds ~30% to judge prompt length, marginal cost.
- **Combined source count can grow**: a polluted prompt may now have static + LLM sources on the same axis. Aggregator handles this fine (same tanh formula), but the report's "Top sources" table may have more rows. UX-wise this is **good** (more evidence) but the rewriter's suggestions need top-N truncation regardless (Bug 2 in acceptance review).

### Neutral / future-proofing

- The `EvidenceContributor` protocol is intentionally trivial (one method, one return type). When v0.3 adds `EmbeddingContributor`, no protocol change needed.
- Keeps the door open for **per-source provenance reporting** (the HTML report can color-code sources by contributor).

## 5. Migration plan

Order matters; each step independently runnable.

1. **Rename + reshape protocol** (no behavior change yet)
   - `Engine` → `EvidenceContributor`, add deprecation alias.
   - `read_axes` → `contribute`, return `Dict[Axis, List[PollutionSource]]`.
   - `StaticEngine` reuses existing rule-matching, just emits sources without doing the aggregation.
   - Aggregator (the existing tanh + baseline math) moves out of `StaticEngine` into `detector._aggregate_to_readings`.
2. **Rewrite `LLMJudgeContributor`**
   - New judge prompt asks for sources + confidence + no-signal axes.
   - New parser produces `Dict[Axis, List[PollutionSource]]` directly.
   - Drop `_build_synthetic_source` — no longer needed.
3. **Refactor `detector.detect_readings`**
   - Accepts `contributors` list.
   - Calls each, merges per-axis source lists, aggregates.
   - `diagnose()` builds the contributor list from `llm_augment` arg.
4. **Update CLI**
   - `--engine` removed; `--llm-augment` added.
   - Old judge flags renamed with deprecation aliases.
   - Fallback logic simplified: just catch `EngineUnavailable` and skip the LLM contributor silently (or emit a one-line "LLM judge skipped" note if `--verbose`).
5. **Rewrite tests**
   - `tests/test_engines.py` becomes `tests/test_contributors.py`.
   - Add hybrid integration tests: static-only, llm-only-via-fake, both-combined.
   - Add the 4 acceptance bugs as regression tests **before** fixing them, prove they fail under v0.2.0.dev0 code path, prove they pass under hybrid.
6. **Apply Bug 2 fix (suggestions top-N) and Bug 3 (alignment hidden when trivial)** in the same PR — independent of hybrid but discovered together.
7. **Update docs**
   - `ARCHITECTURE.md`: replace Engine layering with Contributor layering.
   - `README.md`: replace `--engine` examples with `--llm-augment`.
   - `CHANGELOG.md`: under v0.2.0.dev0, mark the `--engine` variant as "experimental, superseded by hybrid"; add hybrid entry.
   - 知乎 article: align "v0.2 layered" framing with what's actually shipping.

Estimated work: 4–6 hours coding + 1 hour doc updates + re-running the 15-case stress test for verification.

## 6. Open questions / future ADRs

- **OQ-1**: Should `EmbeddingContributor` (v0.3) replace `LLMJudgeContributor` when LLM is unavailable, or stack alongside it? Probable answer: stack, same hybrid principle. Defer to v0.3 ADR.
- **OQ-2**: How do we visualize multi-contributor evidence in the HTML report? Color by contributor? Group by axis? Defer until UI redesign.
- **OQ-3**: The judge prompt currently uses a single LLM call. With many axes, a per-axis call might be more reliable but 8x more expensive. Stay with one-shot for v0.2; revisit if accuracy issues surface in calibration.

## 7. Approval

Awaiting user approval before code changes begin. No code modified by this ADR alone.

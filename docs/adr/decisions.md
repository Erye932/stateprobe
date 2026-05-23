# StateProbe Decision Log

Record every significant project decision here. Each entry should explain what was decided, why, and what alternatives were rejected.

## 001 — DeepSeek-first positioning (2026-05-16)

**Decision**: StateProbe focuses on DeepSeek models first, not all LLMs.

**Why**: A narrow focus creates a stronger identity, makes demos more concrete, and avoids competing with generic eval platforms. DeepSeek has real community attention and open-weight models for local probing.

**Rejected**: Generic multi-model positioning (too scattered, no identity).

## 002 — Visibility-first, engineering-grounded operating rule (2026-05-17)

**Decision**: Every task must improve visibility, usefulness, evidence, contribution readiness, or DeepSeek-first focus. Must pass at least two of the five gates.

**Why**: The project must earn attention first (packaging, demos, shareable cases), then retain it through real engineering and reproducible data. Neither pure hype nor pure tech-for-tech works alone.

**Rejected**: Engineering-only approach (invisible). Hype-only approach (no retention).

## 003 — 1k stars as 90-day target (2026-05-17)

**Decision**: Target 1k GitHub stars in 90 days. DeepSeek official interaction is a stretch goal, not a requirement.

**Why**: 1k is ambitious but realistic with consistent benchmark output, public writing, and X/知乎 presence. 10k requires external luck (viral post, official retweet). 1k is within our control if execution is disciplined.

**Rejected**: 10k target (too dependent on external factors for a primary goal).

## 004 — Project moved to D:\projects\stateprobe (2026-05-17)

**Decision**: Move project from C:\Users\Administrator\Desktop\stateprobe to D:\projects\stateprobe. All model weights, caches, and virtual environments go to D:\caches\.

**Why**: C drive has no space. D drive has 700+ GB. Model weights (7B 4bit ≈ 6GB, venv ≈ 8GB) need stable storage.

## 005 — Case workflow: AI drafts, user reviews (2026-05-17)

**Decision**: AI generates benchmark case drafts. User reviews and approves before merge.

**Why**: Fastest way to produce cases while preserving human judgment and avoiding pure-AI-generated feel. User's domain knowledge is the quality filter.

## 006 — Pure open source, MIT or Apache-2.0 (2026-05-17)

**Decision**: Project is pure open source. No commercial features, no paid tiers.

**Why**: User wants to be seen as an open-source contributor. Commercial complexity would dilute that positioning.

## 007 — X as primary distribution, 知乎 as secondary (2026-05-17)

**Decision**: English posts on X first, Chinese posts on 知乎 second. Handle: Erye932 across all platforms.

**Why**: X is where the international DeepSeek community is. 知乎 is the strongest Chinese developer platform the user has access to. 小红书 is deprioritized (rate-limited). WeChat is deprioritized (no audience).

## 008 — GPU constraint: 4060 Ti 8GB (2026-05-17)

**Decision**: DeepSeek Lab targets DeepSeek-R1-Distill-Qwen-1.5B first, then 7B 4bit quantized. 14B+ deferred.

**Why**: 8GB VRAM can comfortably run 1.5B and 7B 4bit. Larger models need more VRAM than available. Start small, prove the pipeline, then scale if GPU access improves.

## 009 — v0.2 hybrid engine (rejecting --engine switch) (2026-05-17)

**Decision**: v0.2 evidence layer combines static rules and LLM judge **additively** into the same per-axis source pool. Drop the `--engine static|llm` switch. New flag: `--llm-augment` (default off). Static structural + static rules always run; LLM judge contributes additional evidence when enabled and available.

**Why**: Acceptance stress test ([`v02_acceptance_review.md`](../archive/v0.2/acceptance_review.md)) showed each engine has blind spots the other catches: static catches structural attacks (`请请请请...`) and explicit keywords; LLM catches polite implicit pressure («多看到积极的一面»). A switch loses one half. The article's framing ("v0.2 LLM 默认 + static 兜底") was wrong — the right model is layered evidence, not engine replacement.

**Rejected**:
- *Switch (current v0.2.0.dev0 implementation)*: forces user to choose between rule coverage and semantic coverage; LLM mode breaks `is_trivial` because LLM always emits sources for all 8 axes regardless of confidence.
- *Pure LLM replacement*: misses structural attacks LLM can't see; expensive ($X per check); 200x slower for trivial prompts.
- *Static-only forever*: leaves the polite-sycophancy gap that motivated v0.2.

**Detail**: [`009-hybrid-engine.md`](009-hybrid-engine.md) — full code interface and migration plan.

# Changelog

All notable changes to StateProbe will be documented in this file.

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

### Known limitations

- Static Mode is a proxy signal and does not read hidden states.
- Local activation probing is experimental and currently covers only a subset of axes.
- Public benchmark and calibrated accuracy metrics are not yet included.
- GitHub repository URLs are placeholders until the public repo exists.

# stateprobe/enterprise

Placeholder package for the StateProbe enterprise line (Runtime Probe).

Nothing is implemented here. This directory exists to:

- reserve the `stateprobe.enterprise` import path
- make the two-line architecture visible (Skill + Enterprise)
- fail loudly if anything tries to use a Runtime Probe API too early

For the actual direction, non-goals, and the relationship to the
existing Lab layer, see [`../../docs/ENTERPRISE_RUNTIME_PROBE.md`](../../docs/ENTERPRISE_RUNTIME_PROBE.md).

For the shipped product line, see [`../../docs/SKILL_ATTENTION_HUD.md`](../../docs/SKILL_ATTENTION_HUD.md)
and [`../skill/`](../skill/).

# Contributing to StateProbe

Thanks for considering a contribution. StateProbe now has two clearly separated lines:

- **Skill — Agent Attention HUD**: an external control layer for agents. It helps a host decide whether to continue, rewrite, ask the user, or cut stale context before output.
- **Enterprise — Runtime Probe**: the future model-internal line for open-weight activations, vectors, logits, and router traces. This is not implemented yet.

Contributions should improve clarity, evidence, reliability, or developer usability without blurring that boundary.

## What contributions are welcome

- New prompt failure patterns with clear evidence
- Better static rules with fewer false positives
- Demo cases that show real prompt-induced behavior problems
- Skill / MCP integration improvements with tests
- Clearer docs for agent hosts and Claude Code / Cursor users
- Documentation that makes the project easier to trust
- Tests for detector, CLI, eval scaffolding, and lab scaffolding
- Improvements to the evidence model or benchmark roadmap

## Quality bar

Before opening a PR, run:

```bash
python scripts/acceptance_check.py
```

A PR should not be considered ready if it:

- Adds a claim that exceeds the evidence model
- Adds a feature without docs or a demo path
- Breaks `stateprobe check` offline usage
- Breaks `stateprobe skill preview` / `stateprobe skill overlay`
- Makes the Skill line sound like model-internal activation access
- Makes Static Mode sound like hidden-state access
- Adds rules without explanations

## Development setup

```bash
git clone https://github.com/Erye932/stateprobe.git
cd stateprobe
python -m pip install -e ".[dev]"
python -m pytest tests -q
python scripts/acceptance_check.py
```

Optional lab dependencies:

```bash
python -m pip install -e ".[lab]"
```

## Rule contribution format

Every rule should include:

- Pattern or phrase family
- Axis affected
- Direction: `+1` or `-1`
- Weight
- Mechanism explanation
- Citation or rationale
- At least one demo or test if the behavior is important

## Evidence discipline

StateProbe uses multiple evidence layers:

- Static prompt signals
- Black-box output behavior
- Local activation probing
- Skill-level task attention preview / overlay

Do not imply that Static Mode or the Skill line reads closed-source model activations. See `docs/EVIDENCE_MODEL.md`, `docs/SKILL_ATTENTION_HUD.md`, and `docs/ENTERPRISE_RUNTIME_PROBE.md` for the boundary.

## Pull request checklist

- [ ] Tests pass
- [ ] Skill / MCP tests pass if agent-facing behavior changed
- [ ] `python scripts/acceptance_check.py` passes
- [ ] README or docs updated if user-facing behavior changed
- [ ] Demo updated if the change affects project positioning
- [ ] No API keys, generated reports, model weights, or private data committed

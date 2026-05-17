# Contributing to StateProbe

Thanks for considering a contribution. StateProbe is a debugger for prompt-induced LLM behavior, so contributions should improve clarity, evidence, reliability, or developer usability.

## What contributions are welcome

- New prompt failure patterns with clear evidence
- Better static rules with fewer false positives
- Demo cases that show real prompt-induced behavior problems
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
- Makes Static Mode sound like hidden-state access
- Adds rules without explanations

## Development setup

```bash
git clone https://github.com/yourname/stateprobe.git
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

StateProbe uses three evidence layers:

- Static prompt signals
- Black-box output behavior
- Local activation probing

Do not imply that Static Mode reads closed-source model activations. See `docs/EVIDENCE_MODEL.md` for the boundary.

## Pull request checklist

- [ ] Tests pass
- [ ] `python scripts/acceptance_check.py` passes
- [ ] README or docs updated if user-facing behavior changed
- [ ] Demo updated if the change affects project positioning
- [ ] No API keys, generated reports, model weights, or private data committed

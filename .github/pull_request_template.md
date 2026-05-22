## Summary

What changed?

## Why

What problem does this solve?

## Evidence boundary

- [ ] This does not imply the Skill line reads hidden states or neural attention.
- [ ] This does not imply Static Mode reads hidden states.
- [ ] Claims are consistent with `docs/EVIDENCE_MODEL.md`.
- [ ] Skill / Runtime Probe boundaries are consistent with `docs/SKILL_ATTENTION_HUD.md` and `docs/ENTERPRISE_RUNTIME_PROBE.md`.
- [ ] Limitations are documented if needed.

## Tests

- [ ] `python -m pytest tests -q`
- [ ] `python -m pytest tests/test_skill.py tests/test_mcp_server.py -q` if Skill / MCP changed
- [ ] `python scripts/acceptance_check.py`

## Documentation

- [ ] README updated if first-screen or user-facing behavior changed
- [ ] Docs updated if architecture, evidence, or workflow changed
- [ ] Demo updated if positioning changed

## Risk

What could this break or mislead users about?

# Publishing StateProbe

This guide describes the safe path from local project to public GitHub repository and, later, PyPI.

Current GitHub launch focus:

- **Primary shipped value**: Skill — Agent Attention HUD, the external control layer for agent hosts.
- **Secondary shipped value**: `stateprobe check`, the prompt and LLM behavior debugger.
- **Long-term direction**: Enterprise Runtime Probe for open-weight model internals. This is documented as direction only, not shipped implementation.

## Before publishing

Run the full acceptance check:

```bash
python scripts/acceptance_check.py
```

The project should have zero failures. Warnings must be understood before launch.

## Secret safety

Never paste or commit:

- GitHub personal access tokens
- DeepSeek API keys
- OpenAI API keys
- `.env` files
- private prompts or generated reports with sensitive data

If a token is ever pasted into chat, terminal history, an issue, or a committed file, revoke it immediately and generate a new one.

## Recommended GitHub authentication

Use GitHub CLI or a credential manager instead of embedding tokens in commands or files.

```bash
gh auth login
```

Then create or connect a repository using standard GitHub CLI or web UI flows.

## Repository URL check

Before public launch, confirm repository URLs in `pyproject.toml`, `CITATION.cff`, README badges, and GitHub templates point to:

```text
https://github.com/Erye932/stateprobe
```

If a placeholder URL exists anywhere else, replace it before publishing.

## Local preflight

```bash
python -m pytest tests -q
python -m pytest tests/test_skill.py tests/test_mcp_server.py -q
python scripts/acceptance_check.py
stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
stateprobe skill preview --context-text "核心是让 agent 注意力可见。" --plan-text "我准备写 prompt 模板。"
```

## Suggested first commit

```bash
git add .
git commit -m "Initial StateProbe open-source release"
```

## GitHub launch checklist

- README renders correctly on GitHub.
- README first screen clearly says Skill is available and Runtime Probe is future direction.
- CI runs and passes.
- Issue templates appear in the GitHub UI.
- PR template appears when opening a pull request.
- No generated reports or secrets are present.
- Placeholder URLs are replaced.
- `docs/SKILL_ATTENTION_HUD.md` and `docs/MCP_SERVER.md` explain the external control layer clearly.
- `docs/ENTERPRISE_RUNTIME_PROBE.md` does not imply implementation is shipped.
- Release checklist is reviewed.

## PyPI publishing later

PyPI publishing is optional and should happen after the GitHub release is stable.

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Do not publish to PyPI until the package name, README, URLs, and version are final.

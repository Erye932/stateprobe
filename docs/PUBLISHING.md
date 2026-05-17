# Publishing StateProbe

This guide describes the safe path from local project to public GitHub repository and, later, PyPI.

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

## Repository URL update

Before public launch, replace placeholder URLs in `pyproject.toml` and GitHub templates:

```text
https://github.com/yourname/stateprobe
```

with the real repository URL.

## Local preflight

```bash
python -m pytest tests -q
python scripts/acceptance_check.py
stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
```

## Suggested first commit

```bash
git add .
git commit -m "Initial StateProbe open-source release"
```

## GitHub launch checklist

- README renders correctly on GitHub.
- CI runs and passes.
- Issue templates appear in the GitHub UI.
- PR template appears when opening a pull request.
- No generated reports or secrets are present.
- Placeholder URLs are replaced.
- Release checklist is reviewed.

## PyPI publishing later

PyPI publishing is optional and should happen after the GitHub release is stable.

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Do not publish to PyPI until the package name, README, URLs, and version are final.

# Security Policy

StateProbe is a local-first developer tool. The default `stateprobe check` command does not call external APIs.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

Please report security issues privately by opening a GitHub security advisory after the public repository exists.

Until then, do not publish exploit details in public issues.

## Sensitive data rules

Do not commit:

- API keys
- `.env` files
- private prompts containing secrets
- generated reports with sensitive customer data
- downloaded model weights

The repository `.gitignore` should exclude common secret and generated artifact patterns.

## API usage

`stateprobe eval run` may call external OpenAI-compatible APIs. Users should pass credentials through environment variables such as `DEEPSEEK_API_KEY` or `OPENAI_API_KEY`, not hardcode them in code or docs.

## Model weights

`stateprobe lab` can use local open-weight models. Model weights should not be committed to this repository.

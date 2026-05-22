---
name: Bug report
description: Report something that is broken or misleading
title: "[Bug]: "
labels: [bug]
---

## What happened?

Describe the bug clearly.

## Reproduction

```bash
stateprobe check "..."
# or:
stateprobe skill preview --context-text "..." --plan-text "..."
```

## Expected behavior

What did you expect StateProbe to report?

## Actual behavior

What did StateProbe report instead?

## Evidence type

Which mode is affected?

- [ ] Static Mode
- [ ] Black-box Eval
- [ ] DeepSeek Lab
- [ ] Skill preview / overlay
- [ ] MCP server
- [ ] Documentation
- [ ] CLI / packaging

## Environment

- OS:
- Python version:
- StateProbe version:

## Additional context

If this is a false positive or false negative, include the prompt and explain why the diagnosis is wrong.
